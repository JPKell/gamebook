"""Validation, references and gbx tooling."""

from typing import Literal

from pydantic import Field

from gamebook.core.gbx.scope import Context
from gamebook.schemas.common import In, Out


class ProblemOut(Out):
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    act_id: str | None
    node_id: str | None
    choice_id: str | None
    entity_type: str | None
    entity_id: str | None
    field: str | None


class ProblemCounts(Out):
    errors: int
    warnings: int
    info: int


class ProblemsOut(Out):
    counts: ProblemCounts
    problems: list[ProblemOut]


class RefOut(Out):
    source_type: str
    source_id: str
    book_id: str | None
    node_id: str | None
    node_title: str | None = None
    role: str
    field: str
    qty: int | None


class WhereUsed(Out):
    target_type: str
    target_key: str
    refs: list[RefOut]
    #: Sum of quantities for item placements/grants/stock (None if not an item).
    total_qty: int | None = None


class FlagUsage(Out):
    flag: str
    set_count: int
    cleared_count: int
    tested_count: int


class GbxCheckIn(In):
    source: str = Field(max_length=2000)
    context: Context
    book_id: str | None = None
    series_id: str | None = None
    tier: str | None = None


class GbxDiagnosticOut(Out):
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    start: int
    end: int


class GbxCheckOut(Out):
    ok: bool
    diagnostics: list[GbxDiagnosticOut]
    #: Canonical formatting of the expression.
    normalized: str | None = None
    english: str | None = None
    #: [min, max] for numeric expressions when bounded.
    range: tuple[int, int] | None = None
    #: value → probability for pure dice sums.
    distribution: dict[int, float] | None = None
