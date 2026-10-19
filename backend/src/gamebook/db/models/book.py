"""Books and acts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gamebook.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from gamebook.db.models.node import Node
    from gamebook.db.models.series import Series


class Book(IdMixin, TimestampMixin, Base):
    __tablename__ = "book"
    __table_args__ = (UniqueConstraint("series_id", "key"),)

    series_id: Mapped[str] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    number: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    synopsis: Mapped[str] = mapped_column(Text, default="")
    style_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    #: Trim, margins and bleed in mm (``core.art.PageSetup``); print sizes derive from it.
    print_setup: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    #: Print section numbering: the shuffle seed and the stable ``section key → number`` map.
    print_seed: Mapped[int] = mapped_column(Integer, default=1)
    print_numbers: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    start_node_id: Mapped[str | None] = mapped_column(
        ForeignKey("node.id", ondelete="SET NULL", use_alter=True)
    )

    series: Mapped[Series] = relationship(back_populates="books")
    acts: Mapped[list[Act]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Act.position",
    )
    nodes: Mapped[list[Node]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Node.book_id",
    )


class Act(IdMixin, TimestampMixin, Base):
    __tablename__ = "act"
    __table_args__ = (UniqueConstraint("book_id", "key"),)

    book_id: Mapped[str] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(200))
    color: Mapped[str | None] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text, default="")

    book: Mapped[Book] = relationship(back_populates="acts")
    beats: Mapped[list[StoryBeat]] = relationship(
        back_populates="act",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="StoryBeat.position",
    )


class StoryBeat(IdMixin, TimestampMixin, Base):
    """One beat of an act's outline, linked to the nodes that tell it (SPEC §2.7)."""

    __tablename__ = "story_beat"

    act_id: Mapped[str] = mapped_column(ForeignKey("act.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")

    act: Mapped[Act] = relationship(back_populates="beats")
    links: Mapped[list[BeatNode]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="BeatNode.position"
    )

    @property
    def node_ids(self) -> list[str]:
        return [link.node_id for link in self.links]


class BeatNode(Base):
    __tablename__ = "story_beat_node"

    beat_id: Mapped[str] = mapped_column(
        ForeignKey("story_beat.id", ondelete="CASCADE"), primary_key=True
    )
    node_id: Mapped[str] = mapped_column(
        ForeignKey("node.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
