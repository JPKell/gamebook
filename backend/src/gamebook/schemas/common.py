"""Base classes and shared field types for API/service schemas."""

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from gamebook.core.keys import KEY_PATTERN

Key = Annotated[str, StringConstraints(pattern=KEY_PATTERN)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class In(BaseModel):
    """Request body: unknown fields are rejected so typos surface."""

    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="after")
    @classmethod
    def _utc(cls, value: Any) -> Any:
        """SQLite drops timezones: stored times are UTC, so say so (clients parse ISO)."""
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class Reorder(In):
    ids: list[str]
