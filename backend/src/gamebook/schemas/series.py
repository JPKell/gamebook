from datetime import datetime
from typing import Literal

from pydantic import Field

from gamebook.core.rules import RuleSystemDef
from gamebook.schemas.common import In, Key, Out, Title


class StyleGuide(In):
    """How prose should read. The LLM writer always receives it (Phase 7)."""

    pov: Literal["second", "first", "third"] = "second"
    tense: Literal["present", "past"] = "present"
    word_min: int = Field(default=150, ge=0)
    word_max: int = Field(default=400, ge=0)
    voice: str = ""
    notes: str = ""


class StyleOverrides(In):
    pov: Literal["second", "first", "third"] | None = None
    tense: Literal["present", "past"] | None = None
    word_min: int | None = Field(default=None, ge=0)
    word_max: int | None = Field(default=None, ge=0)
    voice: str | None = None
    notes: str | None = None


class SeriesCreate(In):
    title: Title
    key: Key | None = None
    description: str = ""
    style: StyleGuide = Field(default_factory=StyleGuide)


class SeriesUpdate(In):
    title: Title | None = None
    key: Key | None = None
    description: str | None = None
    style: StyleGuide | None = None


class BookSummary(Out):
    id: str
    key: str
    number: int | None
    title: str


class SeriesSummary(Out):
    id: str
    key: str
    title: str
    description: str
    updated_at: datetime


class SeriesOut(SeriesSummary):
    style: StyleGuide
    created_at: datetime
    books: list[BookSummary]


class RuleSystemCreate(In):
    name: Title
    key: Key | None = None
    definition: RuleSystemDef | None = Field(
        default=None, description="Omit to start from the default template"
    )
    is_active: bool = False


class RuleSystemUpdate(In):
    name: Title | None = None
    key: Key | None = None
    definition: RuleSystemDef | None = None
    is_active: bool | None = None


class RuleSystemOut(Out):
    id: str
    series_id: str
    key: str
    name: str
    is_active: bool
    definition: RuleSystemDef
    updated_at: datetime
