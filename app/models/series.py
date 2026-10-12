"""
Series model.

Defines the Series table — the top-level container for a shared gamebook
world. A series owns locations, items, and encounters that are available
to all books within it. It also stores tone and worldGuidelines that
serve as context for AI story generation across all books.

Relationships:
  - Series.books: One-to-many to Book models.
  - Series.shared_locations: One-to-many to Location models (where series_id is set).
  - Series.shared_items: One-to-many to Item models (where series_id is set).
  - Series.shared_encounters: One-to-many to Encounter models (where series_id is set).
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Series(Base):
    __tablename__ = "series"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    worldGuidelines: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships — populated when loading series with options=joinedload, etc.
    books: Mapped[List["app.models.book.Book"]] = relationship(
        "Book", back_populates="series", cascade="all, delete-orphan"
    )
    shared_locations: Mapped[List["app.models.location.Location"]] = relationship(
        "Location", foreign_keys="Location.series_id", cascade="all, delete-orphan"
    )
    shared_items: Mapped[List["app.models.item.Item"]] = relationship(
        "Item", foreign_keys="Item.series_id", cascade="all, delete-orphan"
    )
    shared_encounters: Mapped[List["app.models.encounter.Encounter"]] = relationship(
        "Encounter", foreign_keys="Encounter.series_id", cascade="all, delete-orphan"
    )
