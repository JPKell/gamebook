"""Undo/redo per book and whole-database checkpoints."""

from datetime import datetime

from fastapi import APIRouter, status

from gamebook.api.deps import DatabaseDep, SessionDep
from gamebook.db.models import Book
from gamebook.schemas.common import In, Out, Title
from gamebook.services import checkpoints, history
from gamebook.services.common import require

router = APIRouter(tags=["history"])


class HistoryOut(Out):
    can_undo: bool
    can_redo: bool
    undo_label: str | None
    redo_label: str | None
    depth: int


class HistoryStep(HistoryOut):
    #: The change that was undone/redone.
    applied: str


def _state(session: SessionDep, book_id: str) -> HistoryOut:
    return HistoryOut.model_validate(history.state(session, book_id), from_attributes=True)


@router.get("/books/{book_id}/history", response_model=HistoryOut)
def get_history(book_id: str, session: SessionDep) -> HistoryOut:
    require(session, Book, book_id)
    return _state(session, book_id)


@router.post("/books/{book_id}/undo", response_model=HistoryStep)
def undo(book_id: str, session: SessionDep) -> HistoryStep:
    require(session, Book, book_id)
    applied = history.undo(session, book_id)
    return HistoryStep(applied=applied, **_state(session, book_id).model_dump())


@router.post("/books/{book_id}/redo", response_model=HistoryStep)
def redo(book_id: str, session: SessionDep) -> HistoryStep:
    require(session, Book, book_id)
    applied = history.redo(session, book_id)
    return HistoryStep(applied=applied, **_state(session, book_id).model_dump())


# ── checkpoints ──────────────────────────────────────────────────────────


class CheckpointIn(In):
    name: Title


class CheckpointOut(Out):
    id: str
    name: str
    created_at: datetime
    size: int


@router.get("/checkpoints", response_model=list[CheckpointOut])
def list_checkpoints(db: DatabaseDep) -> list[checkpoints.Checkpoint]:
    return checkpoints.list_all(db)


@router.post("/checkpoints", response_model=CheckpointOut, status_code=status.HTTP_201_CREATED)
def create_checkpoint(data: CheckpointIn, db: DatabaseDep) -> checkpoints.Checkpoint:
    return checkpoints.create(db, data.name)


@router.post("/checkpoints/{checkpoint_id}/restore", response_model=CheckpointOut)
def restore_checkpoint(checkpoint_id: str, db: DatabaseDep) -> checkpoints.Checkpoint:
    """Restore the whole database. Returns the safety checkpoint taken first."""
    return checkpoints.restore(db, checkpoint_id)


@router.delete("/checkpoints/{checkpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_checkpoint(checkpoint_id: str, db: DatabaseDep) -> None:
    checkpoints.delete(db, checkpoint_id)
