"""
Book model.

Defines the Book table — a single gamebook within a series. Each book
has its own story graph (acts, nodes, choices) but shares locations,
items, and encounters with other books in the same series.

Relationships:
  - Book.series: Many-to-one to Series (the series this book belongs to).
  - Book.acts: One-to-many to Act models.
  - Book.nodes: One-to-many to Node models.
  - Book.book_locations: One-to-many to Location models (book-specific).
  - Book.book_items: One-to-many to Item models (book-specific).
  - Book.book_encounters: One-to-many to Encounter models (book-specific).

Validation rules enforced at the API level:
  - Choices must target nodes within the same book.
  - Acts must have sequential order numbers with no gaps.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Book(Base):
    __tablename__ = "book"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("series.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    series: Mapped["app.models.series.Series"] = relationship(
        "Series", back_populates="books"
    )
    acts: Mapped[List["app.models.act.Act"]] = relationship(
        "Act", back_populates="book", cascade="all, delete-orphan"
    )
    nodes: Mapped[List["app.models.node.Node"]] = relationship(
        "Node", back_populates="book", cascade="all, delete-orphan"
    )
    book_locations: Mapped[List["app.models.location.Location"]] = relationship(
        "Location", foreign_keys="Location.book_id", cascade="all, delete-orphan"
    )
    book_items: Mapped[List["app.models.item.Item"]] = relationship(
        "Item", foreign_keys="Item.book_id", cascade="all, delete-orphan"
    )
    book_encounters: Mapped[List["app.models.encounter.Encounter"]] = relationship(
        "Encounter", foreign_keys="Encounter.book_id", cascade="all, delete-orphan"
    )
