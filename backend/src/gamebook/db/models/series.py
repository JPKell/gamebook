"""Series (a shared world) and its rule systems."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gamebook.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from gamebook.db.models.book import Book


class Series(IdMixin, TimestampMixin, Base):
    __tablename__ = "series"

    key: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    #: Style guide for prose (pov, tense, word range, voice, notes).
    style: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    #: Prose pipeline settings: models per role, threshold, iterations (SPEC §4.5).
    writing: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    books: Mapped[list[Book]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Book.number",
    )
    rule_systems: Mapped[list[RuleSystem]] = relationship(
        back_populates="series", cascade="all, delete-orphan", passive_deletes=True
    )


class RuleSystem(IdMixin, TimestampMixin, Base):
    __tablename__ = "rule_system"
    __table_args__ = (UniqueConstraint("series_id", "key"),)

    series_id: Mapped[str] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    #: ``gamebook.core.rules.RuleSystemDef`` as JSON.
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)

    series: Mapped[Series] = relationship(back_populates="rule_systems")
