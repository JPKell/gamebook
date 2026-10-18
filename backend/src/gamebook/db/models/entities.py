"""Series entities: shared (book_id NULL) or specific to one book.

``series_id`` is always set so keys are unique per series across both scopes,
which keeps key references in expressions unambiguous.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from gamebook.db.base import Base, IdMixin, TimestampMixin


class ScopedMixin(IdMixin, TimestampMixin):
    @declared_attr.directive
    def __table_args__(cls) -> tuple[Any, ...]:  # noqa: N805
        return (UniqueConstraint("series_id", "key"),)

    series_id: Mapped[str] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), index=True)
    book_id: Mapped[str | None] = mapped_column(
        ForeignKey("book.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))


class Enemy(ScopedMixin, Base):
    __tablename__ = "enemy"

    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    default_level: Mapped[int] = mapped_column(Integer, default=1)
    stat_formulas: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    abilities: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    loot: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    lore_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("lore_entry.id", ondelete="SET NULL")
    )


class Item(ScopedMixin, Base):
    __tablename__ = "item"

    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(16), default="treasure")
    slot: Mapped[str | None] = mapped_column(String(64))
    stackable: Mapped[bool] = mapped_column(Boolean, default=False)
    max_stack: Mapped[int | None] = mapped_column(Integer)
    value: Mapped[int] = mapped_column(Integer, default=0)
    uses: Mapped[int | None] = mapped_column(Integer)
    modifiers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    use_effects: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class RandomTable(ScopedMixin, Base):
    __tablename__ = "random_table"

    description: Mapped[str] = mapped_column(Text, default="")
    dice: Mapped[str] = mapped_column(String(200), default="1d6")
    entries: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class Character(ScopedMixin, Base):
    __tablename__ = "character"

    role: Mapped[str] = mapped_column(String(200), default="")
    appearance: Mapped[str] = mapped_column(Text, default="")
    voice: Mapped[str] = mapped_column(Text, default="")
    motivations: Mapped[str] = mapped_column(Text, default="")
    secrets: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    relationships: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class LoreEntry(ScopedMixin, Base):
    __tablename__ = "lore_entry"

    type: Mapped[str] = mapped_column(String(16), default="other")
    body: Mapped[str] = mapped_column(Text, default="")
    fields: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
