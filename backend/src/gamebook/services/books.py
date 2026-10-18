"""Book and act use-cases."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gamebook.db.models import Act, Book, Node, Series, TextVariant
from gamebook.schemas.book import ActCreate, ActUpdate, BookCreate, BookUpdate
from gamebook.services import refs
from gamebook.services.common import apply_order, assign_key, next_position, require
from gamebook.services.errors import ConflictError, InvalidError


def create_book(session: Session, series_id: str, data: BookCreate) -> Book:
    require(session, Series, series_id)
    number = data.number
    if number is None:
        current = session.scalar(select(func.max(Book.number)).where(Book.series_id == series_id))
        number = (current or 0) + 1
    book = Book(
        series_id=series_id,
        key=assign_key(session, Book, data.key, data.title, series_id=series_id),
        number=number,
        title=data.title,
        synopsis=data.synopsis,
        style_overrides={},
    )
    session.add(book)
    session.flush()
    # Every book starts with one act and a start node, so it's playable at once.
    act = Act(book_id=book.id, key="act_1", position=0, title="Act 1", summary="")
    session.add(act)
    session.flush()
    start = Node(book_id=book.id, act_id=act.id, key="start", title="Start", x=0.0, y=0.0)
    start.variants.append(TextVariant(label="Default", position=0))
    session.add(start)
    session.flush()
    book.start_node_id = start.id
    refs.reindex_node_tree(session, start)
    return book


def update_book(session: Session, book_id: str, data: BookUpdate) -> Book:
    book = require(session, Book, book_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("key") is not None:
        book.key = assign_key(
            session, Book, data.key, book.title, exclude_id=book.id, series_id=book.series_id
        )
    for field in ("title", "number", "synopsis"):
        if field in changes and (changes[field] is not None or field == "number"):
            setattr(book, field, changes[field])
    if data.style_overrides is not None:
        book.style_overrides = data.style_overrides.model_dump(exclude_none=True)
    if "start_node_id" in changes:
        if data.start_node_id is not None:
            node = require(session, Node, data.start_node_id)
            if node.book_id != book.id:
                raise InvalidError("The start node must belong to this book", field="start_node_id")
        book.start_node_id = data.start_node_id
    session.flush()
    return book


def delete_book(session: Session, book_id: str) -> None:
    book = require(session, Book, book_id)
    series_id = book.series_id
    book.start_node_id = None
    session.flush()
    session.delete(book)
    session.flush()
    # Book-specific entities went with the book; other books' references to
    # them (validation errors already) must not keep stale index rows.
    session.expire_all()
    refs.rebuild_series(session, series_id)


# ── acts ─────────────────────────────────────────────────────────────────


def create_act(session: Session, book_id: str, data: ActCreate) -> Act:
    require(session, Book, book_id)
    act = Act(
        book_id=book_id,
        key=assign_key(session, Act, data.key, data.title, book_id=book_id),
        position=next_position(session, Act.position, book_id=book_id),
        title=data.title,
        color=data.color,
        summary=data.summary,
    )
    session.add(act)
    session.flush()
    return act


def update_act(session: Session, act_id: str, data: ActUpdate) -> Act:
    act = require(session, Act, act_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("key") is not None:
        act.key = assign_key(
            session, Act, data.key, act.title, exclude_id=act.id, book_id=act.book_id
        )
    for field in ("title", "summary"):
        if changes.get(field) is not None:
            setattr(act, field, changes[field])
    if "color" in changes:
        act.color = data.color
    session.flush()
    return act


def delete_act(session: Session, act_id: str, *, force: bool = False) -> None:
    act = require(session, Act, act_id)
    nodes = list(session.scalars(select(Node).where(Node.act_id == act_id)))
    if nodes and not force:
        raise ConflictError(
            f"{act.title} still has {len(nodes)} node(s); move them or delete with force",
            node_count=len(nodes),
        )
    book = require(session, Book, act.book_id)
    from gamebook.services.nodes import delete_nodes  # local: avoid import cycle

    delete_nodes(session, book, nodes)
    session.delete(act)
    session.flush()
    remaining = sorted(book.acts, key=lambda a: a.position)
    for pos, a in enumerate(x for x in remaining if x.id != act_id):
        a.position = pos
    session.flush()


def reorder_acts(session: Session, book_id: str, ids: list[str]) -> list[Act]:
    book = require(session, Book, book_id)
    apply_order(list(book.acts), ids)
    session.flush()
    return sorted(book.acts, key=lambda a: a.position)
