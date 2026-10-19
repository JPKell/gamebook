"""LLM players: a model plays the book as a reader (SPEC §5.4).

Each step the model sees the reader's page (``render_page``), its own running
notes and the numbered options, and answers with JSON. The engine rolls every die,
so the model can only choose. Runs are stored as pick indices like bot runs (they
replay exactly), plus the player's notes per step and what the run cost.

Games run in parallel up to the provider's concurrency. Each finished run is saved
straight away, so a cancelled, failed or over-budget batch can be resumed: the
resume plays the runs that are missing or were stopped part-way.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from gamebook.core.engine.bundle import from_bundle
from gamebook.core.engine.events import Action, Event
from gamebook.core.engine.game import Game
from gamebook.core.engine.narrate import Names
from gamebook.core.model import BookSnapshot
from gamebook.core.sim import RunRecord, summarize
from gamebook.core.sim.batch import StopRun, play_with
from gamebook.core.sim.reader import render_page
from gamebook.db.models import Book, LlmProvider, PlaytestBatch, PlaytestRun
from gamebook.db.session import Database
from gamebook.jobs import JobContext
from gamebook.llm.client import LlmError
from gamebook.llm.templates import PERSONAS, PLAYER_SCHEMA
from gamebook.schemas.llm import RoleModel, WritingSettings
from gamebook.schemas.playtest import LlmPlayer
from gamebook.services import llm, play
from gamebook.services.common import require
from gamebook.services.errors import InvalidError

#: Games played at once, at most (and never more than the provider allows).
MAX_PARALLEL = 4
#: The model's running notes are cut to this (bounds the prompt).
MEMORY_CHARS = 600
NOTE_CHARS = 500
#: The page and each option label are cut to these (long prose must not blow the context).
PAGE_CHARS = 12_000
OPTION_CHARS = 200
#: Model calls failing this many times in a row (any game) stop the batch.
MAX_FAILURES = 3
#: Outcomes a resume plays again: cut short by a cap, a cancel or a failing model.
REPLAYABLE = ("stopped", "llm_error")


def check_player(session: Session, player: LlmPlayer) -> LlmProvider:
    p = session.get(LlmProvider, player.provider_id)
    if p is None:
        raise InvalidError("That provider doesn't exist", field="player.provider_id")
    if not p.enabled:
        raise InvalidError(f"The provider {p.name} is disabled", field="player.provider_id")
    listed = [str(m.get("id")) for m in p.models or []]
    if listed and player.model not in listed:
        raise InvalidError(f"{p.name} has no model {player.model!r}", field="player.model")
    return p


def _clip(value: Any, cap: int = NOTE_CHARS) -> str:
    return (value if isinstance(value, str) else "" if value is None else str(value))[:cap]


def _safe(text: str, cap: int) -> str:
    """Clip, and keep the prompt's own markers out of book text."""
    return text[:cap].replace("</page>", "</ page>").replace("</options>", "</ options>")


class Shared:
    """State shared by a batch's games: spending against the cap, and a stop switch."""

    def __init__(self, spent: float, cap: float | None) -> None:
        self.spent, self.cap = spent, cap
        self.halted: str | None = None
        self._failures = 0
        self._lock = threading.Lock()

    def add(self, cost: float) -> None:
        with self._lock:
            self.spent += cost

    def exhausted(self) -> bool:
        with self._lock:
            return self.cap is not None and self.spent >= self.cap

    def halt(self, reason: str) -> None:
        with self._lock:
            self.halted = self.halted or reason

    def failed(self, reason: str) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= MAX_FAILURES and self.halted is None:
                self.halted = f"The model failed {self._failures} times in a row: {reason}"

    def succeeded(self) -> None:
        with self._lock:
            self._failures = 0


@dataclass
class _Run:
    """One game's model player: its notes, memory and cost."""

    db: Database
    batch_id: str
    player: LlmPlayer
    settings: WritingSettings
    scope: llm.CallScope
    shared: Shared
    should_stop: Any  # () -> bool: the job was cancelled
    prose: dict[str, str]
    beat_notes: dict[str, str]
    names: Names | None = None
    memory: str = ""
    cost: float = 0.0
    notes: list[dict[str, Any]] = field(default_factory=list)
    #: Why the model failed this run (it ends as ``llm_error``, replayed on resume).
    error: str | None = None

    def _spend(self, cost: float) -> None:
        if not cost:
            return
        self.cost += cost
        self.shared.add(cost)
        # The batch's spend is a running total, written per call: it survives a
        # crash mid-run and runs being replaced on resume.
        with self.db.session() as s:
            s.execute(
                update(PlaytestBatch)
                .where(PlaytestBatch.id == self.batch_id)
                .values(cost_usd=PlaytestBatch.cost_usd + cost)
            )

    def _stop_if_needed(self) -> None:
        if self.should_stop() or self.shared.exhausted() or self.shared.halted:
            raise StopRun

    def _call(self, variables: dict[str, Any], **extra: Any) -> tuple[dict[str, Any], str]:
        self._stop_if_needed()
        try:
            data, res = llm.call_json(
                self.db,
                role="player",
                variables=variables,
                settings=self.settings,
                scope=self.scope,
                json_schema=PLAYER_SCHEMA,
                **extra,
            )
        except LlmError as exc:
            self._spend(exc.cost_usd)
            raise
        self._spend(res.cost_usd)
        return data, res.text

    def choose(self, game: Game, options: list[Action], events: list[Event]) -> int:
        self._stop_if_needed()
        self.names = self.names or Names.for_game(game)
        page = render_page(
            game,
            options,
            events,
            names=self.names,
            prose=self.prose,
            beat_notes=self.beat_notes,
        )
        labels = [_safe(o, OPTION_CHARS) for o in page.options]
        variables = {
            "persona": PERSONAS[self.player.persona],
            "memory": self.memory,
            "page": _safe(page.text, PAGE_CHARS),
            "options": labels,
        }
        try:
            data, text = self._call(variables)
            pick = _pick(data, len(options))
            if pick is None:  # one more try, telling it what went wrong
                data, _ = self._call(
                    variables,
                    previous=text,
                    nudge=f"That isn't one of the options. Reply with the same JSON and a "
                    f'"choice" from 1 to {len(options)}.',
                )
                pick = _pick(data, len(options))
                if pick is None:
                    raise LlmError(
                        f"The player chose {data.get('choice')!r} of {len(options)} options"
                    )
        except LlmError as exc:
            self.error = str(exc)
            self.shared.failed(str(exc))
            raise StopRun from exc
        self.shared.succeeded()
        self.memory = _clip(data.get("memory"), MEMORY_CHARS)
        confusion = _clip(data.get("confusion")).strip()
        self.notes.append(
            {
                "step": len(self.notes),
                "node_id": game.state.node_id,
                "choice": pick,
                "option": labels[pick],
                "reasoning": _clip(data.get("reasoning")),
                "confused": bool(data.get("confused")) or bool(confusion),
                "confusion": confusion,
            }
        )
        return pick


def _pick(data: dict[str, Any], n: int) -> int | None:
    choice = data.get("choice")
    if isinstance(choice, str) and choice.strip().isdigit():
        choice = int(choice.strip())
    if isinstance(choice, float) and choice.is_integer():
        choice = int(choice)
    if isinstance(choice, bool) or not isinstance(choice, int) or not 1 <= choice <= n:
        return None
    return choice - 1


# ── batches ──────────────────────────────────────────────────────────────


def _todo(s: Session, b: PlaytestBatch) -> list[int]:
    """Run indices still to play: missing ones, and ones cut short (replayed fresh).

    Their spend stays in the batch's running total.
    """
    s.execute(
        delete(PlaytestRun).where(PlaytestRun.batch_id == b.id, PlaytestRun.outcome.in_(REPLAYABLE))
    )
    done = set(s.scalars(select(PlaytestRun.index).where(PlaytestRun.batch_id == b.id)))
    return [i for i in range(b.n_runs) if i not in done]


def batch_job(batch_id: str) -> Any:
    """The job body for an LLM batch (or its resume)."""

    def run(ctx: JobContext) -> dict[str, Any]:
        db = ctx.db
        with db.session() as s:
            b = require(s, PlaytestBatch, batch_id)
            b.status = "running"
            book_row = s.get(Book, b.book_id)
            player = LlmPlayer.model_validate(
                {k: v for k, v in b.player.items() if k != "budget_usd"}
            )
            provider = check_player(s, player)
            llm.ensure_templates(s)  # once, before the games race to seed them
            parallel = max(1, min(MAX_PARALLEL, provider.max_concurrency))
            todo = _todo(s, b)
            done_before = b.n_runs - len(todo)
            tier, seed_base, max_steps = b.tier, b.seed_base, b.max_steps
            shared = Shared(b.cost_usd, b.player.get("budget_usd"))
            scope = llm.CallScope(
                series_id=book_row.series_id if book_row else None,
                book_id=b.book_id,
                job_id=ctx.job_id,
            )
            book = from_bundle(b.bundle)
            prose = play.prose_for(s, [v.id for n in book.nodes for v in n.variants])
            beat_notes = play.beat_notes_for(s, [n.id for n in book.nodes])
        settings = WritingSettings(
            roles={
                "player": RoleModel(
                    provider_id=player.provider_id,
                    model=player.model,
                    temperature=player.temperature,
                    max_tokens=player.max_tokens,
                )
            }
        )
        started = time.monotonic()
        lock = threading.Lock()
        total = done_before + len(todo)
        finished = done_before

        def one(index: int) -> None:
            nonlocal finished
            seat = _Run(
                db=db,
                batch_id=batch_id,
                player=player,
                settings=settings,
                scope=scope,
                shared=shared,
                should_stop=ctx.cancelled,
                prose=prose,
                beat_notes=beat_notes,
            )
            rec = play_with(
                book, tier, seed_base + index, seat.choose, max_steps=max_steps, index=index
            )
            if seat.error is not None:
                rec.outcome, rec.error_sample = "llm_error", seat.error[:500]
            with db.session() as s:
                s.add(
                    PlaytestRun(
                        batch_id=batch_id,
                        **rec.stored(),
                        notes=seat.notes,
                        cost_usd=round(seat.cost, 6),
                    )
                )
            with lock:
                finished += 1
                ctx.progress(finished, total, force=True)

        ctx.progress(done_before, total, force=True)
        crash: BaseException | None = None
        try:
            with ThreadPoolExecutor(max_workers=parallel, thread_name_prefix="llm-player") as pool:
                for fut in as_completed([pool.submit(one, i) for i in todo]):
                    try:
                        fut.result()
                    except Exception as exc:  # stop the other games; report after the summary
                        crash = crash or exc
                        shared.halt(f"{type(exc).__name__}: {exc}")
        finally:
            # The summary covers what was played, however the job ends.
            with db.session() as s:
                kept = s.get(PlaytestBatch, batch_id)
                if kept is not None:  # None: deleted while running
                    kept.summary = rebuild_summary(s, kept)
                    kept.duration_s = round((kept.duration_s or 0) + time.monotonic() - started, 3)
        if crash is not None:
            raise crash
        ctx.check()  # cancelled: the finished runs are kept; resume plays the rest
        if shared.halted:
            raise LlmError(f"{shared.halted}. Fix the provider, then resume the batch.")
        with db.session() as s:
            b = require(s, PlaytestBatch, batch_id)
            b.status = "stopped" if shared.exhausted() and _cut_short(s, b) else "done"
            win_rate, cost, status = (b.summary or {}).get("win_rate"), b.cost_usd, b.status
        return {"batch_id": batch_id, "win_rate": win_rate, "cost_usd": cost, "status": status}

    return run


def _cut_short(s: Session, b: PlaytestBatch) -> bool:
    n = s.scalar(
        select(func.count()).where(
            PlaytestRun.batch_id == b.id, PlaytestRun.outcome.in_(REPLAYABLE)
        )
    )
    return bool(n)


def _replayed(book: BookSnapshot, tier: str, run: PlaytestRun, max_steps: int) -> RunRecord:
    """A stored run's full record, rebuilt by replaying its picks."""
    picks = iter(run.picks)

    def chooser(_g: Game, _o: list[Action], _e: list[Event]) -> int:
        try:
            return next(picks)
        except StopIteration:
            raise StopRun from None

    rec = play_with(book, tier, run.seed, chooser, max_steps=max_steps, index=run.index)
    if run.outcome in ("error", *REPLAYABLE):  # how it ended isn't in the picks
        rec.outcome, rec.errors, rec.error_sample = run.outcome, run.errors, run.error_sample
    return rec


def rebuild_summary(s: Session, b: PlaytestBatch) -> dict[str, Any]:
    """Summary of every stored run (all of them, across resumes), plus confusion notes."""
    book = from_bundle(b.bundle)
    runs = list(
        s.scalars(
            select(PlaytestRun).where(PlaytestRun.batch_id == b.id).order_by(PlaytestRun.index)
        )
    )
    summary = summarize(book, [_replayed(book, b.tier, r, b.max_steps) for r in runs])
    by_node: dict[str, dict[str, Any]] = {}
    steps = confused = 0
    for r in runs:
        for note in r.notes or []:
            steps += 1
            if not note.get("confused"):
                continue
            confused += 1
            row = by_node.setdefault(
                note.get("node_id") or "", {"node_id": note.get("node_id"), "count": 0, "notes": []}
            )
            row["count"] += 1
            if note.get("confusion") and len(row["notes"]) < 5:
                row["notes"].append(
                    {"run": r.index, "step": note["step"], "text": note["confusion"]}
                )
    summary["llm"] = {
        "steps": steps,
        "confused_steps": confused,
        "cost_usd": b.cost_usd,
        "stopped_runs": sum(r.outcome == "stopped" for r in runs),
        "failed_runs": sum(r.outcome == "llm_error" for r in runs),
        "confusion": sorted(by_node.values(), key=lambda x: -x["count"])[:50],
    }
    return summary
