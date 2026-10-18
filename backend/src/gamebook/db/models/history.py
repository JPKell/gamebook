"""Per-book undo/redo history (book snapshots)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from gamebook.db.base import Base, utcnow


class HistoryEntry(Base):
    __tablename__ = "history_entry"
    __table_args__ = (Index("ix_history_entry_book_stack", "book_id", "stack", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"))
    #: "undo" or "redo"
    stack: Mapped[str] = mapped_column(String(8))
    #: What the change was, e.g. "Edit node 'Hall'" (shown as "Undo Edit node 'Hall'").
    label: Mapped[str] = mapped_column(String(200))
    #: ``export.tree.export_book`` output: the book *before* the change.
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
