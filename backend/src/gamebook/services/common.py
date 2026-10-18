"""Helpers shared by services."""

import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gamebook.core.keys import key_problem, slugify, unique_key
from gamebook.db.repository import NotFoundError
from gamebook.services.errors import ConflictError, InvalidError


def require[T](session: Session, model: type[T], id_: str) -> T:
    obj = session.get(model, id_)
    if obj is None:
        raise NotFoundError(model, id_)
    return obj


def taken_keys(session: Session, model: type[Any], **scope: Any) -> set[str]:
    stmt = select(model.key).filter_by(**scope)
    return set(session.scalars(stmt))


def assign_key(
    session: Session,
    model: type[Any],
    requested: str | None,
    title: str,
    *,
    exclude_id: str | None = None,
    **scope: Any,
) -> str:
    """Validate a requested key, or derive a free one from the title."""
    taken = taken_keys(session, model, **scope)
    if exclude_id is not None:
        current = session.get(model, exclude_id)
        if current is not None:
            taken.discard(current.key)
    if requested is not None:
        problem = key_problem(requested)
        if problem:
            raise InvalidError(problem, field="key")
        if requested in taken:
            raise ConflictError(f"Key {requested!r} is already used", field="key")
        return requested
    return unique_key(slugify(title, fallback=model.__tablename__), taken)


def next_position(session: Session, column: Any, **scope: Any) -> int:
    model = column.class_
    stmt = select(func.max(column)).where(*(getattr(model, k) == v for k, v in scope.items()))
    current = session.scalar(stmt)
    return 0 if current is None else current + 1


def apply_order(items: list[Any], ids: list[str]) -> None:
    """Set ``position`` from an explicit id order (must be a permutation)."""
    by_id = {i.id: i for i in items}
    if sorted(ids) != sorted(by_id):
        raise InvalidError("Order must list every item exactly once")
    for pos, id_ in enumerate(ids):
        by_id[id_].position = pos


def key_follows_title(current_key: str, old_title: str, fallback: str) -> bool:
    """True when a key was derived from the title (``slug`` or ``slug_N``), so a
    title change should carry the key along. Hand-picked keys never move."""
    base = slugify(old_title, fallback=fallback)
    return (
        current_key == base or re.fullmatch(rf"{re.escape(base[:60])}_\d+", current_key) is not None
    )
