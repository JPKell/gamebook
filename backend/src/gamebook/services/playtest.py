"""Playtest batches (bots), run replays, the coverage walker, and jobs."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from gamebook.core.engine.bundle import from_bundle, to_bundle
from gamebook.core.model import BookSnapshot
from gamebook.core.sim import RunRecord, replay_run, summarize, walk
from gamebook.db.models import Book, Job, PlaytestBatch, PlaytestRun
from gamebook.db.repository import NotFoundError
from gamebook.db.session import Database
from gamebook.jobs import JobContext, JobRunner
from gamebook.schemas.playtest import (
    BatchDetail,
    BatchIn,
    BatchOut,
    CoverageIn,
    JobOut,
    PlayOut,
    RunOut,
    RunPage,
)
from gamebook.services import play, simpool, snapshot
from gamebook.services.common import require
from gamebook.services.errors import ConflictError, InvalidError

#: Re-exported so the API layer reaches jobs only through services.
Runner = JobRunner


def content(session: Session, book_id: str) -> tuple[BookSnapshot, dict[str, Any], str]:
    """The playable book, its bundle, and the bundle's content hash."""
    book = snapshot.book_snapshot(session, book_id)
    bundle = to_bundle(book)
    digest = hashlib.sha256(
        json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return book, bundle, digest


def _check_playable(book: BookSnapshot, tier: str) -> None:
    if book.rules is None:
        raise InvalidError("The series has no active rule system")
    if tier not in book.rules.tier_keys():
        raise InvalidError(f"Unknown tier {tier!r}", field="tier")
    if book.start_node_id is None:
        raise InvalidError("The book has no start node")


def _job(session: Session, kind: str, label: str, total: int, payload: dict[str, Any]) -> Job:
    job = Job(kind=kind, label=label, total=total, payload=payload)
    session.add(job)
    session.flush()
    return job


# ── batches ──────────────────────────────────────────────────────────────


def create_batch(session: Session, book_id: str, data: BatchIn) -> PlaytestBatch:
    require(session, Book, book_id)
    book, bundle, digest = content(session, book_id)
    _check_playable(book, data.tier)
    bot = data.player.bot
    label = data.label or f"{data.runs:,} {bot} · {data.tier}"
    job = _job(session, "batch", f"Playtest: {label}", data.runs, {"book_id": book_id})
    batch = PlaytestBatch(
        book_id=book_id,
        job_id=job.id,
        label=label,
        tier=data.tier,
        player=data.player.model_dump(),
        n_runs=data.runs,
        seed_base=data.seed_base,
        max_steps=data.max_steps,
        content_hash=digest,
        bundle=bundle,
    )
    session.add(batch)
    session.flush()
    job.payload = {"book_id": book_id, "batch_id": batch.id}
    return batch


def batch_job(batch_id: str, workers: int) -> Any:
    """The job body for one batch (runs in the job thread)."""

    def run(ctx: JobContext) -> dict[str, Any]:
        with ctx.db.session() as s:
            b = require(s, PlaytestBatch, batch_id)
            b.status = "running"
            spec = (b.content_hash, b.bundle, b.tier, b.player["bot"], b.max_steps)
            seeds = [(i, b.seed_base + i) for i in range(b.n_runs)]
        started = time.monotonic()
        records: list[RunRecord] = []
        for chunk in simpool.run_batch(*spec, seeds, workers=workers):
            records += chunk
            ctx.progress(len(records), len(seeds))
            ctx.check()
        records.sort(key=lambda r: r.index)
        summary = summarize(from_bundle(spec[1]), records)
        with ctx.db.session() as s:
            b = require(s, PlaytestBatch, batch_id)
            s.execute(insert(PlaytestRun), [{"batch_id": batch_id, **r.stored()} for r in records])
            b.summary = summary
            b.status = "done"
            b.duration_s = round(time.monotonic() - started, 3)
        ctx.progress(len(records), len(seeds), force=True)
        return {"batch_id": batch_id, "win_rate": summary["win_rate"]}

    return run


def finish_batch(db: Database, batch_id: str) -> Any:
    """Mirror a failed/cancelled job onto its batch."""

    def done(_job_id: str, status: str) -> None:
        if status == "done":
            return
        with db.session() as s:
            b = s.get(PlaytestBatch, batch_id)
            if b is not None:
                b.status = status

    return done


def recover(db: Database) -> int:
    """Batches left queued/running by a previous process failed with their jobs."""
    session = db.session_factory()
    try:
        stale = list(
            session.scalars(
                select(PlaytestBatch).where(PlaytestBatch.status.in_(("queued", "running")))
            )
        )
        for b in stale:
            b.status = "failed"
        if stale:
            session.commit()
        return len(stale)
    finally:
        session.close()


def start_batch(runner: JobRunner, workers: int, batch: PlaytestBatch) -> None:
    assert batch.job_id is not None
    runner.submit(batch.job_id, batch_job(batch.id, workers), finish_batch(runner.db, batch.id))


def _batch_out(b: PlaytestBatch, current_hash: str | None) -> dict[str, Any]:
    return {
        **{c: getattr(b, c) for c in BatchOut.model_fields if hasattr(b, c)},
        "win_rate": (b.summary or {}).get("win_rate"),
        "stale": current_hash is not None and b.content_hash != current_hash,
    }


def _current_hash(session: Session, book_id: str) -> str | None:
    try:
        return content(session, book_id)[2]
    except Exception:  # an unplayable book just means "can't tell"
        return None


def list_batches(session: Session, book_id: str) -> list[BatchOut]:
    require(session, Book, book_id)
    current = _current_hash(session, book_id)
    rows = session.scalars(
        select(PlaytestBatch)
        .where(PlaytestBatch.book_id == book_id)
        .order_by(PlaytestBatch.created_at.desc())
    )
    return [BatchOut.model_validate(_batch_out(b, current)) for b in rows]


def _names(bundle: dict[str, Any]) -> dict[str, dict[str, str]]:
    book = bundle.get("book", {})
    return {
        "nodes": {n["id"]: n["title"] for n in book.get("nodes", [])},
        "acts": {a["id"]: a["title"] for a in book.get("acts", [])},
        "items": {i["key"]: i["name"] for i in book.get("items", [])},
        "enemies": {e["key"]: e["name"] for e in book.get("enemies", [])},
    }


def get_batch(session: Session, batch_id: str) -> BatchDetail:
    b = require(session, PlaytestBatch, batch_id)
    job = session.get(Job, b.job_id) if b.job_id else None
    return BatchDetail.model_validate(
        {
            **_batch_out(b, _current_hash(session, b.book_id)),
            "summary": b.summary,
            "job": JobOut.model_validate(job) if job else None,
            "names": _names(b.bundle),
        }
    )


def delete_batch(session: Session, runner: JobRunner, batch_id: str) -> None:
    b = require(session, PlaytestBatch, batch_id)
    if b.status in ("queued", "running") and b.job_id:
        runner.cancel(b.job_id)
    job_id = b.job_id
    session.execute(delete(PlaytestRun).where(PlaytestRun.batch_id == batch_id))
    session.delete(b)
    if job_id and b.status not in ("queued", "running"):
        session.execute(delete(Job).where(Job.id == job_id))


def list_runs(
    session: Session, batch_id: str, outcome: str | None, offset: int, limit: int
) -> RunPage:
    require(session, PlaytestBatch, batch_id)
    q = select(PlaytestRun).where(PlaytestRun.batch_id == batch_id)
    if outcome:
        q = q.where(PlaytestRun.outcome == outcome)
    total = session.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = session.scalars(q.order_by(PlaytestRun.index).offset(offset).limit(limit))
    return RunPage(total=total, runs=[RunOut.model_validate(r) for r in rows])


def replay(session: Session, batch_id: str, index: int, upto: int | None) -> PlayOut:
    """A stored run, replayed against the bundle it was played on, after ``upto`` steps."""
    b = require(session, PlaytestBatch, batch_id)
    run = session.scalar(
        select(PlaytestRun).where(PlaytestRun.batch_id == batch_id, PlaytestRun.index == index)
    )
    if run is None:
        raise NotFoundError(PlaytestRun, str(index))
    picks = run.picks if upto is None else run.picks[: max(0, upto)]
    book = from_bundle(b.bundle)
    game = replay_run(book, b.tier, run.seed, [])
    turns = [-1] * len(game.log)
    for i, pick in enumerate(picks):
        mark = len(game.log)
        options = game.available()
        if not 0 <= pick < len(options):
            raise ConflictError(
                f"Run {index + 1} can't be replayed past step {i}: the engine has changed "
                "since this batch ran"
            )
        game.step(options[pick])
        turns += [i] * (len(game.log) - mark)
    ids = [game.state.node_id] if game.state.node_id else []
    return play.view(
        game,
        turns=turns,
        applied=len(picks),
        error=None,
        beat_notes=play.beat_notes_for(session, ids),
        prose=play.prose_for(session, [game.state.variant_id] if game.state.variant_id else []),
    )


# ── coverage ─────────────────────────────────────────────────────────────


def create_coverage(session: Session, book_id: str, data: CoverageIn) -> Job:
    require(session, Book, book_id)
    book, _bundle, _ = content(session, book_id)
    _check_playable(book, data.tier)
    return _job(
        session,
        "coverage",
        f"Coverage walk · {data.tier}",
        data.max_states,
        {"book_id": book_id, **data.model_dump()},
    )


def coverage_job(book_id: str, data: CoverageIn) -> Any:
    def run(ctx: JobContext) -> dict[str, Any]:
        with ctx.db.session() as s:
            book, _bundle, digest = content(s, book_id)

        def progress(states: int) -> None:
            ctx.progress(states, data.max_states)
            ctx.check()

        res = walk(
            book, data.tier, max_states=data.max_states, samples=data.samples, on_progress=progress
        )
        ctx.progress(res.states, data.max_states, force=True)
        return {
            "tier": data.tier,
            "content_hash": digest,
            "states": res.states,
            "truncated": res.truncated,
            "reached": sorted(res.reached),
            "unreached": [n.id for n in book.nodes if n.id not in res.reached],
            "endings": {k: sorted(v) for k, v in sorted(res.endings.items())},
            "other_endings": sorted(res.other_endings),
            "nodes_total": len(book.nodes),
        }

    return run


# ── jobs ─────────────────────────────────────────────────────────────────


def get_job(session: Session, job_id: str) -> Job:
    return require(session, Job, job_id)


def cancel_job(session: Session, runner: JobRunner, job_id: str) -> Job:
    job = require(session, Job, job_id)
    if job.status not in ("queued", "running"):
        raise ConflictError(f"The job is already {job.status}")
    runner.cancel(job_id)
    return job
