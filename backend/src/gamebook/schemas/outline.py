"""Act outlines (story beats) and the state digest."""

from typing import Literal

from pydantic import Field

from gamebook.schemas.common import In, Out, Title


class BeatCreate(In):
    title: Title = "New beat"
    description: str = ""
    node_ids: list[str] = Field(default_factory=list, max_length=500)


class BeatUpdate(In):
    title: Title | None = None
    description: str | None = None
    node_ids: list[str] | None = Field(default=None, max_length=500)


class BeatOut(Out):
    id: str
    act_id: str
    position: int
    title: str
    description: str
    node_ids: list[str]


class OutlineAct(Out):
    id: str
    key: str
    title: str
    color: str | None
    summary: str
    position: int
    beats: list[BeatOut]


class OutlineOut(Out):
    book_id: str
    acts: list[OutlineAct]


# ── state digest ─────────────────────────────────────────────────────────


class FactOut(Out):
    key: str
    label: str


class FactsOut(Out):
    flags: list[FactOut] = Field(default_factory=list)
    items: list[FactOut] = Field(default_factory=list)
    characters: list[FactOut] = Field(default_factory=list)
    skills: list[FactOut] = Field(default_factory=list)


class GateOut(Out):
    choice_id: str
    label: str
    condition: str
    #: always: every reader can take it · never: no reader can · depends: some can.
    verdict: Literal["always", "never", "depends"]


class NodeDigestOut(Out):
    node_id: str
    reachable: bool
    depth_min: int | None
    #: None when a loop makes the longest route unbounded.
    depth_max: int | None
    canonical_predecessor_auto: str | None
    canonical_predecessor_override: str | None
    #: The override when set, otherwise the automatic choice.
    canonical_predecessor: str | None
    must: FactsOut
    #: Possible on some routes but not all (``must`` excluded).
    may: FactsOut
    gates: list[GateOut]


class BookDigestOut(Out):
    tier: str
    nodes: dict[str, NodeDigestOut]
