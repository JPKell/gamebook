"""Books, acts, the graph view and validation."""

from fastapi import APIRouter, Query, status

from gamebook.api.deps import SessionDep
from gamebook.core.analysis import validate_book
from gamebook.db.models import Act, Book, Series
from gamebook.schemas.analysis import ProblemCounts, ProblemOut, ProblemsOut
from gamebook.schemas.book import (
    ActCreate,
    ActOut,
    ActUpdate,
    BookCreate,
    BookGraph,
    BookOut,
    BookUpdate,
)
from gamebook.schemas.common import Reorder
from gamebook.schemas.node import DuplicateRequest, DuplicateResult, LayoutUpdate, NodeOut
from gamebook.schemas.series import BookSummary
from gamebook.services import assist, history, snapshot, writing
from gamebook.services import books as svc
from gamebook.services import nodes as node_svc
from gamebook.services.common import require

router = APIRouter(tags=["books"])


@router.get("/series/{series_id}/books", response_model=list[BookSummary])
def list_books(series_id: str, session: SessionDep) -> list[Book]:
    return list(require(session, Series, series_id).books)


@router.post(
    "/series/{series_id}/books", response_model=BookOut, status_code=status.HTTP_201_CREATED
)
def create_book(series_id: str, data: BookCreate, session: SessionDep) -> Book:
    return svc.create_book(session, series_id, data)


@router.get("/books/{book_id}", response_model=BookOut)
def get_book(book_id: str, session: SessionDep) -> Book:
    return require(session, Book, book_id)


@router.patch("/books/{book_id}", response_model=BookOut)
def update_book(book_id: str, data: BookUpdate, session: SessionDep) -> Book:
    history.record(session, book_id, "Edit book")
    return svc.update_book(session, book_id, data)


@router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: str, session: SessionDep) -> None:
    svc.delete_book(session, book_id)


@router.get("/books/{book_id}/graph", response_model=BookGraph)
def get_book_graph(book_id: str, session: SessionDep) -> BookGraph:
    book = require(session, Book, book_id)
    return BookGraph(
        book=BookOut.model_validate(book),
        acts=[ActOut.model_validate(a) for a in book.acts],
        nodes=[NodeOut.model_validate(n) for n in snapshot.load_book_nodes(session, book_id)],
    )


@router.get("/books/{book_id}/problems", response_model=ProblemsOut)
def get_book_problems(book_id: str, session: SessionDep) -> ProblemsOut:
    snap = snapshot.book_snapshot(session, book_id)  # shared by both checks
    problems = (
        validate_book(snap)
        + writing.stale_problems(session, book_id, snap)
        + assist.finding_problems(session, book_id)
    )
    return ProblemsOut(
        counts=ProblemCounts(
            errors=sum(p.severity == "error" for p in problems),
            warnings=sum(p.severity == "warning" for p in problems),
            info=sum(p.severity == "info" for p in problems),
        ),
        problems=[ProblemOut.model_validate(p) for p in problems],
    )


@router.put("/books/{book_id}/layout", status_code=status.HTTP_204_NO_CONTENT)
def save_layout(book_id: str, data: LayoutUpdate, session: SessionDep) -> None:
    history.record(session, book_id, "Move nodes")
    node_svc.save_layout(session, book_id, data)


@router.post("/books/{book_id}/duplicate", response_model=DuplicateResult)
def duplicate_nodes(book_id: str, data: DuplicateRequest, session: SessionDep) -> DuplicateResult:
    history.record(session, book_id, f"Duplicate {len(data.node_ids)} node(s)")
    return DuplicateResult(mapping=node_svc.duplicate_nodes(session, book_id, data))


# ── acts ─────────────────────────────────────────────────────────────────


@router.post("/books/{book_id}/acts", response_model=ActOut, status_code=status.HTTP_201_CREATED)
def create_act(book_id: str, data: ActCreate, session: SessionDep) -> Act:
    history.record(session, book_id, f"Add act '{data.title}'")
    return svc.create_act(session, book_id, data)


@router.put("/books/{book_id}/acts/order", response_model=list[ActOut])
def reorder_acts(book_id: str, data: Reorder, session: SessionDep) -> list[Act]:
    history.record(session, book_id, "Reorder acts")
    return svc.reorder_acts(session, book_id, data.ids)


@router.patch("/acts/{act_id}", response_model=ActOut)
def update_act(act_id: str, data: ActUpdate, session: SessionDep) -> Act:
    history.record_for(session, Act, act_id, "Edit act")
    return svc.update_act(session, act_id, data)


@router.delete("/acts/{act_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_act(act_id: str, session: SessionDep, force: bool = Query(default=False)) -> None:
    history.record_for(session, Act, act_id, "Delete act")
    svc.delete_act(session, act_id, force=force)
