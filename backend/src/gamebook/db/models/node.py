"""Nodes and everything that hangs off them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gamebook.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from gamebook.db.models.book import Book


class Node(IdMixin, TimestampMixin, Base):
    __tablename__ = "node"
    __table_args__ = (UniqueConstraint("book_id", "key"),)

    book_id: Mapped[str] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    act_id: Mapped[str] = mapped_column(ForeignKey("act.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    beat_notes: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    is_act_entry: Mapped[bool] = mapped_column(Boolean, default=False)
    is_act_exit: Mapped[bool] = mapped_column(Boolean, default=False)
    ending_kind: Mapped[str | None] = mapped_column(String(16))
    ending_grade: Mapped[str | None] = mapped_column(String(16))
    ending_label: Mapped[str] = mapped_column(String(200), default="")
    location_id: Mapped[str | None] = mapped_column(
        ForeignKey("lore_entry.id", ondelete="SET NULL")
    )
    canonical_predecessor_id: Mapped[str | None] = mapped_column(
        ForeignKey("node.id", ondelete="SET NULL")
    )
    style_override: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    section_pin: Mapped[int | None] = mapped_column(Integer)
    on_enter: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    is_shop: Mapped[bool] = mapped_column(Boolean, default=False)
    shop_sell_rate: Mapped[int | None] = mapped_column(Integer)
    x: Mapped[float] = mapped_column(Float, default=0.0)
    y: Mapped[float] = mapped_column(Float, default=0.0)
    collapsed: Mapped[bool] = mapped_column(Boolean, default=False)

    book: Mapped[Book] = relationship(back_populates="nodes", foreign_keys=[book_id])
    variants: Mapped[list[TextVariant]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="TextVariant.position"
    )
    choices: Mapped[list[Choice]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="Choice.position"
    )
    encounters: Mapped[list[Encounter]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="Encounter.position"
    )
    items: Mapped[list[NodeItem]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="NodeItem.position"
    )
    shop_items: Mapped[list[ShopItem]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="ShopItem.position"
    )
    characters: Mapped[list[NodeCharacter]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def character_ids(self) -> list[str]:
        return sorted(c.character_id for c in self.characters)


class NodeCharacter(Base):
    __tablename__ = "node_character"

    node_id: Mapped[str] = mapped_column(
        ForeignKey("node.id", ondelete="CASCADE"), primary_key=True
    )
    character_id: Mapped[str] = mapped_column(
        ForeignKey("character.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class TextVariant(IdMixin, Base):
    __tablename__ = "text_variant"

    node_id: Mapped[str] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(200), default="Default")
    condition: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=0)


class Choice(IdMixin, TimestampMixin, Base):
    __tablename__ = "choice"

    node_id: Mapped[str] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(16), default="goto")
    condition: Mapped[str | None] = mapped_column(Text)
    unmet_display: Mapped[str] = mapped_column(String(16), default="hide")
    print_text: Mapped[str | None] = mapped_column(Text)
    min_tier: Mapped[str | None] = mapped_column(String(64))
    effects: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    dice: Mapped[str | None] = mapped_column(String(200))
    test: Mapped[str | None] = mapped_column(String(64))
    encounter_id: Mapped[str | None] = mapped_column(
        ForeignKey("encounter.id", ondelete="SET NULL")
    )
    flee_allowed: Mapped[bool] = mapped_column(Boolean, default=False)

    outcomes: Mapped[list[ChoiceOutcome]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="ChoiceOutcome.position"
    )


class ChoiceOutcome(IdMixin, Base):
    __tablename__ = "choice_outcome"
    __table_args__ = (UniqueConstraint("choice_id", "key"),)

    choice_id: Mapped[str] = mapped_column(ForeignKey("choice.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    key: Mapped[str] = mapped_column(String(64), default="default")
    target_node_id: Mapped[str | None] = mapped_column(
        ForeignKey("node.id", ondelete="SET NULL"), index=True
    )
    range_lo: Mapped[int | None] = mapped_column(Integer)
    range_hi: Mapped[int | None] = mapped_column(Integer)


class Encounter(IdMixin, Base):
    __tablename__ = "encounter"

    node_id: Mapped[str] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(200), default="")
    mode: Mapped[str] = mapped_column(String(16), default="fixed")
    fight: Mapped[str] = mapped_column(String(16), default="sequential")
    table_id: Mapped[str | None] = mapped_column(
        ForeignKey("random_table.id", ondelete="SET NULL"), index=True
    )

    enemies: Mapped[list[EncounterEnemy]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="EncounterEnemy.position"
    )


class EncounterEnemy(IdMixin, Base):
    __tablename__ = "encounter_enemy"

    encounter_id: Mapped[str] = mapped_column(
        ForeignKey("encounter.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    enemy_id: Mapped[str] = mapped_column(ForeignKey("enemy.id", ondelete="CASCADE"), index=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    count: Mapped[int] = mapped_column(Integer, default=1)


class NodeItem(IdMixin, Base):
    """An item that can be found (and optionally taken) at a node."""

    __tablename__ = "node_item"

    node_id: Mapped[str] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    item_id: Mapped[str] = mapped_column(ForeignKey("item.id", ondelete="CASCADE"), index=True)
    qty: Mapped[int] = mapped_column(Integer, default=1)


class ShopItem(IdMixin, Base):
    __tablename__ = "shop_item"

    node_id: Mapped[str] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    item_id: Mapped[str] = mapped_column(ForeignKey("item.id", ondelete="CASCADE"), index=True)
    price: Mapped[int] = mapped_column(Integer, default=0)
    stock: Mapped[int | None] = mapped_column(Integer)
