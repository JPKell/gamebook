from datetime import datetime

from pydantic import Field

from gamebook.schemas.common import In, Key, Out, Title
from gamebook.schemas.node import NodeOut
from gamebook.schemas.series import StyleOverrides


class BookCreate(In):
    title: Title
    key: Key | None = None
    number: int | None = None
    synopsis: str = ""


class BookUpdate(In):
    title: Title | None = None
    key: Key | None = None
    number: int | None = None
    synopsis: str | None = None
    style_overrides: StyleOverrides | None = None
    start_node_id: str | None = None


class BookOut(Out):
    id: str
    series_id: str
    key: str
    number: int | None
    title: str
    synopsis: str
    style_overrides: StyleOverrides
    start_node_id: str | None
    created_at: datetime
    updated_at: datetime


class ActCreate(In):
    title: Title
    key: Key | None = None
    color: str | None = Field(default=None, max_length=16)
    summary: str = ""


class ActUpdate(In):
    title: Title | None = None
    key: Key | None = None
    color: str | None = Field(default=None, max_length=16)
    summary: str | None = None


class ActOut(Out):
    id: str
    book_id: str
    key: str
    position: int
    title: str
    color: str | None
    summary: str


class BookGraph(Out):
    """Everything the story canvas needs in one response."""

    book: BookOut
    acts: list[ActOut]
    nodes: list[NodeOut]
