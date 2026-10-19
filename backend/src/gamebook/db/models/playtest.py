"""Background jobs and playtest batches/runs (SPEC §2.10, §2.12)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gamebook.db.base import Base, IdMixin, utcnow


class Job(IdMixin, Base):
    __tablename__ = "job"

    kind: Mapped[str] = mapped_column(String(32))
    #: queued | running | done | failed | cancelled
    status: Mapped[str] = mapped_column(String(16), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(200), default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlaytestBatch(IdMixin, Base):
    __tablename__ = "playtest_batch"

    book_id: Mapped[str] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("job.id", ondelete="SET NULL"))
    label: Mapped[str] = mapped_column(String(200), default="")
    tier: Mapped[str] = mapped_column(String(64))
    #: {"kind": "bot", "bot": "random"} (LLM players arrive in Phase 8)
    player: Mapped[dict[str, Any]] = mapped_column(JSON)
    n_runs: Mapped[int] = mapped_column(Integer)
    seed_base: Mapped[int] = mapped_column(Integer, default=1)
    max_steps: Mapped[int] = mapped_column(Integer, default=500)
    #: SHA-256 of the canonical game bundle: same hash, same book and rules.
    content_hash: Mapped[str] = mapped_column(String(64))
    #: The game bundle played (book + rule system), so runs replay exactly later.
    bundle: Mapped[dict[str, Any]] = mapped_column(JSON)
    #: queued | running | done | failed | cancelled
    status: Mapped[str] = mapped_column(String(16), default="queued")
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    duration_s: Mapped[float | None] = mapped_column(Float)
    #: LLM players: total model spend for the batch so far.
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlaytestRun(Base):
    __tablename__ = "playtest_run"
    __table_args__ = (Index("ix_playtest_run_batch_outcome", "batch_id", "outcome"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("playtest_batch.id", ondelete="CASCADE"), index=True
    )
    index: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16))
    ending_node_id: Mapped[str | None] = mapped_column(String(36))
    last_node_id: Mapped[str | None] = mapped_column(String(36))
    steps: Mapped[int] = mapped_column(Integer)
    #: Index into the available actions at each step (replays the run exactly).
    picks: Mapped[list[int]] = mapped_column(JSON)
    death_cause: Mapped[str | None] = mapped_column(String(80))
    errors: Mapped[int] = mapped_column(Integer, default=0)
    error_sample: Mapped[str | None] = mapped_column(Text)
    #: LLM players: per step {step, node_id, choice, reasoning, confused, confusion}.
    notes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
