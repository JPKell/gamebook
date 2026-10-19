"""Artwork: the asset library, placements, maps and appendices (SPEC §2.13-2.14)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from gamebook.db.base import Base, IdMixin, TimestampMixin


class Asset(IdMixin, TimestampMixin, Base):
    """An image in a series' library. The file lives at ``<data_dir>/assets/<sha256>.<ext>``."""

    __tablename__ = "asset"
    #: Identical uploads to one series are the same asset.
    __table_args__ = (UniqueConstraint("series_id", "sha256"),)

    series_id: Mapped[str] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    #: png | jpg | webp
    ext: Mapped[str] = mapped_column(String(8))
    mime: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))
    width_px: Mapped[int] = mapped_column(Integer)
    height_px: Mapped[int] = mapped_column(Integer)
    bytes: Mapped[int] = mapped_column(Integer)
    alt_text: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    credit: Mapped[str] = mapped_column(String(300), default="")
    licence: Mapped[str] = mapped_column(String(200), default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)


class ArtPlacement(IdMixin, TimestampMixin, Base):
    """Where artwork appears: a node, act, book or entity, with print and digital layout.

    ``asset_id`` may be empty: a placeholder with a brief, so books can be laid out
    before the art exists. Exactly one target column matches ``target_type``
    (``book_id`` is also set on node and act placements, for per-book queries).
    """

    __tablename__ = "art_placement"

    series_id: Mapped[str] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), index=True)
    #: node | act | book | character | enemy | item | lore
    target_type: Mapped[str] = mapped_column(String(16))
    book_id: Mapped[str | None] = mapped_column(
        ForeignKey("book.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[str | None] = mapped_column(
        ForeignKey("node.id", ondelete="CASCADE"), index=True
    )
    act_id: Mapped[str | None] = mapped_column(ForeignKey("act.id", ondelete="CASCADE"), index=True)
    character_id: Mapped[str | None] = mapped_column(
        ForeignKey("character.id", ondelete="CASCADE"), index=True
    )
    enemy_id: Mapped[str | None] = mapped_column(
        ForeignKey("enemy.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[str | None] = mapped_column(
        ForeignKey("item.id", ondelete="CASCADE"), index=True
    )
    lore_id: Mapped[str | None] = mapped_column(
        ForeignKey("lore_entry.id", ondelete="CASCADE"), index=True
    )
    #: illustration | opener | cover_front | cover_back | frontispiece | title_page |
    #: endpaper | portrait | image
    role: Mapped[str] = mapped_column(String(16))
    asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("asset.id", ondelete="SET NULL"), index=True
    )
    #: Node placements: only for readers who get this text variant. Deleting the variant
    #: deletes the art (showing it to every reader could spoil the other branches).
    variant_id: Mapped[str | None] = mapped_column(
        ForeignKey("text_variant.id", ondelete="CASCADE")
    )
    #: Only in editions of this tier (None: every tier).
    tier: Mapped[str | None] = mapped_column(String(64))
    #: print | digital | both
    media: Mapped[str] = mapped_column(String(8), default="both")
    position: Mapped[int] = mapped_column(Integer, default=0)
    caption: Mapped[str] = mapped_column(Text, default="")
    #: Commissioning: what the illustrator should draw, and how far along it is.
    brief: Mapped[str] = mapped_column(Text, default="")
    #: needed | sketch | final
    status: Mapped[str] = mapped_column(String(8), default="needed")
    #: Print layout controls (``core.art.PrintLayout``).
    layout: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    #: Digital display (``core.art.DigitalLayout``).
    digital: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Map(IdMixin, TimestampMixin, Base):
    """A map over an image, with markers linking to nodes or lore locations."""

    __tablename__ = "map"
    __table_args__ = (UniqueConstraint("series_id", "key"),)

    series_id: Mapped[str] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), index=True)
    #: None: shared by every book in the series.
    book_id: Mapped[str | None] = mapped_column(
        ForeignKey("book.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("asset.id", ondelete="SET NULL"))
    #: ``[{id, x, y (0-1), label, node_id?, lore_id?, visible_if?}]``
    markers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class Appendix(IdMixin, TimestampMixin, Base):
    """Generated back matter for a book (SPEC §2.14)."""

    __tablename__ = "appendix"

    book_id: Mapped[str] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    #: bestiary | sheet | items | rules | personae | glossary | maps | custom
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    #: ``core.appendix`` options: tier, spoilers, order, stat mode, body…
    options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
