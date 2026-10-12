"""
Item model.

Defines the Item table — an item found or obtained at a story beat.
Items follow the same shared-specific pattern as Location:
  - series_id IS NOT NULL → shared across all books in the series.
  - book_id IS NOT NULL (series_id IS NULL) → specific to this book.

Each item has a name, description, and an optional effect field
(stored as JSON for flexible stat modifiers like attack bonus, healing, etc.).

Relationships:
  - Items are referenced by nodes via the items JSON field.
  - During authoring, the frontend tracks which items are available at
    each node. In a future phase, a junction table could replace the
    JSON storage for stricter integrity.
"""

from typing import Optional

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Item(Base):
    __tablename__ = "item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("series.id"), nullable=True
    )
    book_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("book.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effect: Mapped[Optional[str]] = mapped_column(String, nullable=True)
