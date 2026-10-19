"""Print edition schemas (SPEC §6.3)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from gamebook.schemas.common import In, Out


class ReshuffleIn(In):
    #: A fixed seed (reproducible numbering); omit for a random one.
    seed: int | None = Field(default=None, ge=1, le=2**31 - 1)


class ReshuffleOut(Out):
    seed: int


class PrintWarningOut(Out):
    code: str
    message: str
    node_id: str | None = None
    number: int | None = None


class PrintArtProblem(Out):
    code: str
    severity: str
    message: str
    node_id: str | None = None


class SectionNumber(Out):
    number: int
    node_id: str
    title: str
    #: router | section
    kind: str


class PreflightOut(Out):
    tier: str
    tier_label: str
    seed: int
    sections: int
    routers: int
    tick_boxes: int
    #: Sections still printing beat notes (no approved prose).
    drafts: int
    warnings: list[PrintWarningOut]
    art: list[PrintArtProblem]
    numbers: list[SectionNumber]


class VerifyIn(In):
    tier: str | None = None
    #: Played in the request, so kept modest.
    runs: int = Field(default=200, ge=1, le=500)


class VerifyOut(Out):
    ok: bool
    runs: int
    moves: int
    arrivals: int
    problems: int
    samples: list[str]
    unvisited: list[int]
    structure: list[str]


class ExportIn(In):
    tier: str | None = None
    format: Literal["pdf", "epub"]
