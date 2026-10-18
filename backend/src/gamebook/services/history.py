"""Server-side undo/redo per book.

Before every book-scoped change, ``record`` stores a snapshot of the book's
story graph. Undo restores the latest snapshot (saving the current state for
redo); any new change clears redo. History survives reloads and covers every
kind of edit because it works on whole-book snapshots, not inverse operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from gamebook.db.base import utcnow
from gamebook.db.models import Act, HistoryEntry, Node
from gamebook.export import tree
from gamebook.services.common import require
from gamebook.services.errors import ConflictError

MAX_ENTRIES = 50
#: Edits with the same label this close together share one undo step (typing).
COALESCE_SECONDS = 10


@dataclass(frozen=True)
class HistoryState:
    can_undo: bool
    can_redo: bool
    undo_label: str | None
    redo_label: str | None
    depth: int


def book_id_of(session: Session, model: type[Any], id_: str) -> str:
    """The book a node/choice/variant/encounter/act belongs to."""
    obj = require(session, model, id_)
    if model in (Node, Act):
        return str(obj.book_id)
    node = require(session, Node, obj.node_id)
    return node.book_id


def record(session: Session, book_id: str, label: str) -> None:
    label = label[:200]
    session.execute(
        delete(HistoryEntry).where(HistoryEntry.book_id == book_id, HistoryEntry.stack == "redo")
    )
    last = _latest(session, book_id, "undo")
    if last is not None and last.label == label:
        created = last.created_at if last.created_at.tzinfo else last.created_at.replace(tzinfo=UTC)
        if (utcnow() - created).total_seconds() < COALESCE_SECONDS:
            last.created_at = utcnow()
            session.flush()
            return
    session.add(
        HistoryEntry(
            book_id=book_id, stack="undo", label=label, snapshot=tree.export_book(session, book_id)
        )
    )
    _trim(session, book_id)
    session.flush()


def record_for(session: Session, model: type[Any], id_: str, label: str) -> str:
    book_id = book_id_of(session, model, id_)
    record(session, book_id, label)
    return book_id


def _trim(session: Session, book_id: str) -> None:
    ids = list(
        session.scalars(
            select(HistoryEntry.id)
            .where(HistoryEntry.book_id == book_id, HistoryEntry.stack == "undo")
            .order_by(HistoryEntry.id.desc())
            .offset(MAX_ENTRIES)
        )
    )
    if ids:
        session.execute(delete(HistoryEntry).where(HistoryEntry.id.in_(ids)))


def _latest(session: Session, book_id: str, stack: str) -> HistoryEntry | None:
    return session.scalar(
        select(HistoryEntry)
        .where(HistoryEntry.book_id == book_id, HistoryEntry.stack == stack)
        .order_by(HistoryEntry.id.desc())
        .limit(1)
    )


def _step(session: Session, book_id: str, source: str, target: str) -> str:
    entry = _latest(session, book_id, source)
    if entry is None:
        raise ConflictError(f"Nothing to {source}")
    current = tree.export_book(session, book_id)
    try:
        tree.restore_book(session, book_id, entry.snapshot)
    except tree.TreeError as exc:
        raise ConflictError(
            f"Can't {source} '{entry.label}': it refers to something deleted since ({exc})"
        ) from exc
    session.add(HistoryEntry(book_id=book_id, stack=target, label=entry.label, snapshot=current))
    session.delete(entry)
    session.flush()
    return entry.label


def undo(session: Session, book_id: str) -> str:
    return _step(session, book_id, "undo", "redo")


def redo(session: Session, book_id: str) -> str:
    return _step(session, book_id, "redo", "undo")


def state(session: Session, book_id: str) -> HistoryState:
    undo_top = _latest(session, book_id, "undo")
    redo_top = _latest(session, book_id, "redo")
    depth = session.scalar(
        select(func.count()).where(HistoryEntry.book_id == book_id, HistoryEntry.stack == "undo")
    )
    return HistoryState(
        can_undo=undo_top is not None,
        can_redo=redo_top is not None,
        undo_label=undo_top.label if undo_top else None,
        redo_label=redo_top.label if redo_top else None,
        depth=depth or 0,
    )
