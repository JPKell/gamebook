"""
Location model.

Defines the Location table — a named place within the gamebook world.
Locations can be shared across all books in a series (series_id is set)
or specific to a single book (book_id is set, series_id is null).

The shared-specific pattern:
  - series_id IS NOT NULL, book_id IS NULL → shared across the series.
  - series_id IS NULL, book_id IS NOT NULL → specific to this book.
  - Both being set is not allowed (enforced at the API layer).

Relationships:
  - Location belongs to either a series or a book (not both).
  - Nodes reference a location via locationId (stored as a string ID).
"""

from typing import Optional

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Location(Base):
    __tablename__ = "location"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("series.id"), nullable=True
    )
    book_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("book.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
