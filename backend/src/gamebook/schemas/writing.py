"""Prose versions, review actions, the writing queue and pipeline runs."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from gamebook.schemas.common import In, Out

ProseStatus = Literal["none", "draft", "in_review", "approved", "stale"]


class ProseOut(Out):
    id: str
    node_id: str
    variant_id: str
    text: str
    status: str
    source: str
    pipeline_run_id: str | None
    parent_id: str | None
    inputs_hash: str
    summary: str
    notes: str
    created_at: datetime
    approved_at: datetime | None


class VariantProse(Out):
    variant_id: str
    label: str
    condition: str | None
    status: ProseStatus
    approved: ProseOut | None
    #: Newest version of any status.
    latest: ProseOut | None
    versions: list[ProseOut]


class NodeProse(Out):
    node_id: str
    variants: list[VariantProse]


class QueueRow(Out):
    node_id: str
    node_title: str
    act_id: str
    act_title: str
    variant_id: str
    variant_label: str
    status: ProseStatus
    #: Position in canonical order (act, then distance from the start).
    order: int
    reachable: bool
    words: int
    latest_id: str | None


class QueueOut(Out):
    rows: list[QueueRow]
    counts: dict[str, int]


class ProseCreate(In):
    text: str = Field(min_length=1, max_length=50_000)
    summary: str = Field(default="", max_length=2000)
    approve: bool = False


class ApproveIn(In):
    #: Approve with these edits (saved as a new human version).
    text: str | None = Field(default=None, min_length=1, max_length=50_000)
    summary: str | None = Field(default=None, max_length=2000)


class RejectIn(In):
    notes: str = Field(default="", max_length=2000)


class GenerateIn(In):
    notes: str = Field(default="", max_length=4000)


class ActGenerateIn(In):
    #: missing: no approved or in-review text · stale: approved but stale · all
    only: Literal["missing", "stale", "all"] = "missing"
    max_cost_usd: float | None = Field(default=None, ge=0)


class PipelineRunOut(Out):
    id: str
    node_id: str
    variant_id: str
    status: str
    notes: str
    trail: list[dict[str, Any]]
    iterations: int
    final_score: float | None
    cost_usd: float
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class ContextOut(Out):
    ctx: dict[str, Any]
    sections: dict[str, int]
    tokens: int
    budget: int
    trimmed: list[str]
    inputs_hash: str
