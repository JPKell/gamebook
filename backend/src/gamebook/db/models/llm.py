"""LLM providers, prompt templates, the call log, prose versions and pipeline runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gamebook.db.base import Base, IdMixin, TimestampMixin, utcnow


class LlmProvider(IdMixin, TimestampMixin, Base):
    """An OpenAI-compatible endpoint (local, OpenAI, OpenRouter) or the offline test model."""

    __tablename__ = "llm_provider"

    name: Mapped[str] = mapped_column(String(200))
    #: openai | fake
    kind: Mapped[str] = mapped_column(String(16), default="openai")
    base_url: Mapped[str] = mapped_column(String(500), default="")
    #: Name of the environment variable holding the API key (keys are never stored).
    api_key_env: Mapped[str | None] = mapped_column(String(100))
    #: [{id, label, context_window, input_per_mtok, output_per_mtok}]
    models: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=2)
    timeout_s: Mapped[float] = mapped_column(Float, default=120.0)
    #: Extra request headers (e.g. OpenRouter's HTTP-Referer / X-Title).
    headers: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class PromptTemplate(IdMixin, Base):
    """One version of a role's prompt (Jinja2). Editing creates a new version."""

    __tablename__ = "prompt_template"
    __table_args__ = (Index("ix_prompt_template_role_version", "role", "version", unique=True),)

    #: writer | critic | editor | summarizer | …
    role: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    system: Mapped[str] = mapped_column(Text)
    user: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LlmCall(IdMixin, Base):
    """Every model call, for the log browser and cost tracking."""

    __tablename__ = "llm_call"
    __table_args__ = (Index("ix_llm_call_series_created", "series_id", "created_at"),)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    role: Mapped[str] = mapped_column(String(32))
    template_id: Mapped[str | None] = mapped_column(String(36))
    template_version: Mapped[int | None] = mapped_column(Integer)
    provider_id: Mapped[str | None] = mapped_column(
        ForeignKey("llm_provider.id", ondelete="SET NULL")
    )
    model: Mapped[str] = mapped_column(String(200))
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    response: Mapped[str] = mapped_column(Text, default="")
    #: ok | error
    status: Mapped[str] = mapped_column(String(16), default="ok")
    error: Mapped[str | None] = mapped_column(Text)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    #: Kept (as NULL) when the series is deleted or replaced: the cost history stays.
    series_id: Mapped[str | None] = mapped_column(
        ForeignKey("series.id", ondelete="SET NULL"), index=True
    )
    book_id: Mapped[str | None] = mapped_column(String(36))
    node_id: Mapped[str | None] = mapped_column(String(36), index=True)
    job_id: Mapped[str | None] = mapped_column(String(36))
    pipeline_run_id: Mapped[str | None] = mapped_column(String(36), index=True)


class PipelineRun(IdMixin, Base):
    """One writer → critic → editor run for a text variant."""

    __tablename__ = "pipeline_run"

    book_id: Mapped[str] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str] = mapped_column(String(36), index=True)
    variant_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str | None] = mapped_column(String(36))
    #: running | done | failed | cancelled
    status: Mapped[str] = mapped_column(String(16), default="running")
    notes: Mapped[str] = mapped_column(Text, default="")
    #: [{"kind": "draft"|"critique"|"edit", "text"?, "report"?, "call_id"}]
    trail: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    final_score: Mapped[float | None] = mapped_column(Float)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProseVersion(IdMixin, Base):
    """A version of a text variant's prose (SPEC §2.8).

    ``node_id``/``variant_id`` are soft references: undo rebuilds nodes and
    variants with the same ids, and prose history must survive that.
    """

    __tablename__ = "prose_version"
    __table_args__ = (Index("ix_prose_version_variant", "variant_id", "created_at"),)

    book_id: Mapped[str] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str] = mapped_column(String(36), index=True)
    variant_id: Mapped[str] = mapped_column(String(36))
    text: Mapped[str] = mapped_column(Text)
    #: draft | in_review | approved | rejected | superseded
    status: Mapped[str] = mapped_column(String(16), default="draft")
    #: human | llm
    source: Mapped[str] = mapped_column(String(16), default="human")
    pipeline_run_id: Mapped[str | None] = mapped_column(String(36))
    parent_id: Mapped[str | None] = mapped_column(String(36))
    #: Hash of the context the text was written for (stale when it no longer matches).
    inputs_hash: Mapped[str] = mapped_column(String(64), default="")
    #: Two-to-three sentence summary, fed to later nodes' "story so far".
    summary: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssistItem(IdMixin, Base):
    """Something an assist pipeline proposes, for the author to accept or dismiss.

    ``kind``: ``finding`` (consistency issue on a node) · ``suggestion`` (a draft
    subgraph for an act) · ``lore`` (a new or updated character / lore entry).
    The payload's shape depends on the kind (``schemas/assist.py``).
    """

    __tablename__ = "assist_item"
    __table_args__ = (Index("ix_assist_item_book_kind_status", "book_id", "kind", "status"),)

    book_id: Mapped[str] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    #: open | accepted | partial | rejected | dismissed | superseded
    status: Mapped[str] = mapped_column(String(16), default="open")
    node_id: Mapped[str | None] = mapped_column(String(36), index=True)
    act_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    #: For findings: hash of the prose that was checked (outdated once it changes).
    checked_hash: Mapped[str | None] = mapped_column(String(64))
    job_id: Mapped[str | None] = mapped_column(String(36))
    call_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
