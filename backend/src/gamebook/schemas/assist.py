"""LLM authoring assists: consistency findings, draft subgraphs, lore drafts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from gamebook.schemas.common import In, Out

AssistKind = Literal["finding", "suggestion", "lore"]


class AssistItemOut(Out):
    id: str
    book_id: str
    kind: str
    status: str
    node_id: str | None
    act_id: str | None
    payload: dict[str, Any]
    #: Findings only: the prose has changed since it was checked.
    outdated: bool = False
    created_at: datetime


class ConsistencyIn(In):
    #: Limit to one act (book-wide when omitted). Ignored for node checks.
    act_id: str | None = None


class SuggestIn(In):
    notes: str = Field(default="", max_length=4000)


class ExtractLoreIn(In):
    act_id: str | None = None


class AcceptSuggestionIn(In):
    """Which parts to accept; both empty means everything still pending."""

    nodes: list[str] = Field(default_factory=list, max_length=100)
    choices: list[int] = Field(default_factory=list, max_length=200)


class RejectSuggestionIn(In):
    nodes: list[str] = Field(default_factory=list, max_length=100)
    choices: list[int] = Field(default_factory=list, max_length=200)


class AcceptLoreIn(In):
    #: The author's edits to the proposed fields (name, role, body, …).
    fields: dict[str, str] | None = None


class StatusIn(In):
    status: Literal["dismissed", "rejected", "open"]
