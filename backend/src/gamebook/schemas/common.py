"""Base classes and shared field types for API/service schemas."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from gamebook.core.keys import KEY_PATTERN

Key = Annotated[str, StringConstraints(pattern=KEY_PATTERN)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class In(BaseModel):
    """Request body: unknown fields are rejected so typos surface."""

    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Reorder(In):
    ids: list[str]
