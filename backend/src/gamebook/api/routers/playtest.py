"""In-app player, bot batches, run replays, the coverage walker and jobs."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from gamebook.api.deps import DatabaseDep, SessionDep, SettingsDep
from gamebook.core.sim import BOT_DESCRIPTIONS, BOT_NAMES
from gamebook.db.models import Job
from gamebook.db.repository import NotFoundError
from gamebook.schemas.playtest import (
    BatchDetail,
    BatchIn,
    BatchOut,
    BotOut,
    CoverageIn,
    JobOut,
    PlayIn,
    PlayOut,
    ResumeIn,
    RunPage,
)
from gamebook.services import play, playtest, simpool

router = APIRouter(tags=["playtest"])

#: An SSE stream ends after this long; EventSource clients reconnect.
STREAM_LIMIT_S = 15 * 60


def get_runner(request: Request) -> playtest.Runner:
    runner: playtest.Runner = request.app.state.jobs
    return runner


RunnerDep = Annotated[playtest.Runner, Depends(get_runner)]


@router.get("/playtest/bots", response_model=list[BotOut])
def list_bots() -> list[BotOut]:
    return [BotOut(name=n, description=BOT_DESCRIPTIONS[n]) for n in BOT_NAMES]


@router.post("/books/{book_id}/play", response_model=PlayOut)
def play_book(book_id: str, data: PlayIn, session: SessionDep) -> PlayOut:
    """Replay the reader's inputs from scratch and describe the result."""
    return play.play(session, book_id, data)


# ── batches ──────────────────────────────────────────────────────────────


@router.post("/books/{book_id}/batches", response_model=BatchOut, status_code=201)
def create_batch(
    book_id: str, data: BatchIn, session: SessionDep, runner: RunnerDep, settings: SettingsDep
) -> BatchOut:
    batch = playtest.create_batch(session, book_id, data)
    session.commit()  # the job thread reads the batch
    playtest.start_batch(runner, simpool.processes(settings.sim_processes), batch)
    return BatchOut.model_validate(playtest._batch_out(batch, batch.content_hash))


@router.post("/batches/{batch_id}/resume", response_model=BatchOut)
def resume_batch(
    batch_id: str, data: ResumeIn, session: SessionDep, runner: RunnerDep, settings: SettingsDep
) -> BatchOut:
    """Continue an LLM batch that was cancelled, failed or ran out of budget."""
    batch = playtest.resume_batch(session, batch_id, data)
    session.commit()
    playtest.start_batch(runner, simpool.processes(settings.sim_processes), batch)
    return BatchOut.model_validate(playtest._batch_out(batch, None))


@router.get("/books/{book_id}/batches", response_model=list[BatchOut])
def list_batches(book_id: str, session: SessionDep) -> list[BatchOut]:
    return playtest.list_batches(session, book_id)


@router.get("/batches/{batch_id}", response_model=BatchDetail)
def get_batch(batch_id: str, session: SessionDep) -> BatchDetail:
    return playtest.get_batch(session, batch_id)


@router.delete("/batches/{batch_id}", status_code=204)
def delete_batch(batch_id: str, session: SessionDep, runner: RunnerDep) -> Response:
    playtest.delete_batch(session, runner, batch_id)
    return Response(status_code=204)


@router.get("/batches/{batch_id}/runs", response_model=RunPage)
def list_runs(
    batch_id: str,
    session: SessionDep,
    outcome: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
) -> RunPage:
    return playtest.list_runs(session, batch_id, outcome, offset, limit)


@router.get("/batches/{batch_id}/runs/{index}/replay", response_model=PlayOut)
def replay_run(
    batch_id: str,
    index: int,
    session: SessionDep,
    upto: int | None = Query(default=None, ge=0),
) -> PlayOut:
    """A stored run replayed on the bundle it was played on (optionally after ``upto`` steps)."""
    return playtest.replay(session, batch_id, index, upto)


# ── coverage ─────────────────────────────────────────────────────────────


@router.post("/books/{book_id}/coverage", response_model=JobOut, status_code=201)
def start_coverage(
    book_id: str, data: CoverageIn, session: SessionDep, runner: RunnerDep
) -> JobOut:
    """Start a coverage walk; the result lands on the job."""
    job = playtest.create_coverage(session, book_id, data)
    session.commit()
    runner.submit(job.id, playtest.coverage_job(book_id, data))
    return JobOut.model_validate(job)


# ── jobs ─────────────────────────────────────────────────────────────────


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, session: SessionDep) -> Job:
    return playtest.get_job(session, job_id)


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, session: SessionDep, runner: RunnerDep) -> Job:
    return playtest.cancel_job(session, runner, job_id)


@router.get("/jobs/{job_id}/events", response_class=StreamingResponse)
async def job_events(job_id: str, request: Request, db: DatabaseDep) -> StreamingResponse:
    """Server-sent events: the job (as ``JobOut`` JSON) whenever it changes, until it ends."""
    with db.session() as s:
        playtest.get_job(s, job_id)  # 404 before streaming

    def snapshot() -> dict[str, Any] | None:
        try:
            with db.session() as s:
                return JobOut.model_validate(playtest.get_job(s, job_id)).model_dump(mode="json")
        except NotFoundError:
            return None  # deleted mid-stream (e.g. with its batch)

    async def stream() -> AsyncIterator[str]:
        last = None
        deadline = time.monotonic() + STREAM_LIMIT_S
        while time.monotonic() < deadline and not await request.is_disconnected():
            # Sync DB access stays off the event loop.
            job = await run_in_threadpool(snapshot)
            if job is None:
                return
            if job != last:
                last = job
                yield f"data: {json.dumps(job)}\n\n"
            if job["status"] not in ("queued", "running"):
                return
            await asyncio.sleep(0.3)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )
