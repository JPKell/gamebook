"""
Act model.

Defines the Act table — an ordered grouping of nodes within a book.
Acts represent chapters or sections of a gamebook. Each act has entry
and exit node sets that control how a reader enters and leaves the act.

Constraints:
  - Acts within a book must have unique, sequential order numbers.
  - Each act (except the last) must have at least one exit node.
  - Each act (except the first) must have at least one entry node.
  - The final act of a book may have ending nodes but no exits.

Relationships:
  - Act.book: Many-to-one to Book.
  - Act.nodes: One-to-many to Node models (where node.act_id matches).
"""

from typing import List, Optional

from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Act(Base):
    __tablename__ = "act"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    book_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("book.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    # Stored as JSON arrays of node IDs for fast access.
    # In production, use a separate junction table for stricter integrity.
    entryNodeIds: Mapped[str] = mapped_column(String, default="[]")
    exitNodeIds: Mapped[str] = mapped_column(String, default="[]")
    nodeIds: Mapped[str] = mapped_column(String, default="[]")
    hasEndings: Mapped[bool] = mapped_column(Integer, default=0)

    # Relationship
    book: Mapped["app.models.book.Book"] = relationship(
        "Book", back_populates="acts"
    )
