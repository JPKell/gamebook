"""
Encounter model.

Defines the Encounter table — an enemy or event that can occur at
a story beat. Follows the shared-specific pattern:
  - series_id IS NOT NULL → shared across all books in the series.
  - book_id IS NOT NULL (series_id IS NULL) → specific to this book.

Encounters have optional stats (stored as JSON) for combat resolution
during preview/playthrough modes. The recurring flag indicates whether
the encounter can happen at any node that references it, or only at
the node where it was originally placed.

Relationships:
  - Encounters are referenced by nodes via the encounters JSON field.
"""

from typing import Optional

from sqlalchemy import String, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Encounter(Base):
    __tablename__ = "encounter"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("series.id"), nullable=True
    )
    book_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("book.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stats: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recurring: Mapped[bool] = mapped_column(Integer, default=0)
