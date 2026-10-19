"""Generic use-cases for series entities (enemies, items, tables, characters, lore)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.db.models import Book, Character, Enemy, Item, LoreEntry, RandomTable, Series
from gamebook.services import refs
from gamebook.services.common import assign_key, key_follows_title, require
from gamebook.services.errors import ConflictError, InvalidError
from gamebook.services.refs import SourceType, dump_effects


@dataclass(frozen=True)
class EntityKind:
    name: str  # ref target type, e.g. "item"
    model: type[Any]
    #: Source type for RefIndex when the entity itself holds references.
    source_type: SourceType | None
    #: Fields holding lists of effects (stored as canonical JSON).
    effect_fields: tuple[str, ...] = ()


KINDS: dict[str, EntityKind] = {
    k.name: k
    for k in (
        EntityKind("enemy", Enemy, "enemy"),
        EntityKind("item", Item, "item", ("use_effects",)),
        EntityKind("table", RandomTable, "table"),
        EntityKind("character", Character, "character"),
        EntityKind("lore", LoreEntry, "lore"),
    )
}


def _check_book(session: Session, series_id: str, book_id: str | None) -> None:
    if book_id is not None:
        book = require(session, Book, book_id)
        if book.series_id != series_id:
            raise InvalidError("That book belongs to a different series", field="book_id")


def _dump(kind: EntityKind, data: BaseModel, *, partial: bool) -> dict[str, Any]:
    """Column values from a create/update schema.

    On update, an explicit null clears nullable columns (e.g. ``slot``); for
    non-nullable columns null means "unchanged".
    """
    values = data.model_dump(exclude_unset=partial, exclude={"key", "book_id", "name"})
    columns = kind.model.__table__.c
    out: dict[str, Any] = {}
    for field, value in values.items():
        if value is None:
            if partial and field in columns and columns[field].nullable:
                out[field] = None
            continue
        if field in kind.effect_fields:
            value = dump_effects(getattr(data, field))
        out[field] = value
    return out


def list_entities(
    session: Session,
    kind: EntityKind,
    series_id: str,
    book_id: str | None = None,
    *,
    include_shared: bool = True,
) -> list[Any]:
    require(session, Series, series_id)
    model = kind.model
    stmt = select(model).where(model.series_id == series_id)
    if book_id is not None:
        cond = model.book_id == book_id
        stmt = stmt.where(cond | model.book_id.is_(None) if include_shared else cond)
    return list(session.scalars(stmt.order_by(model.name)))


def _check_lore_link(
    session: Session, series_id: str, book_id: str | None, lore_id: str | None
) -> None:
    if lore_id is None:
        return
    lore = session.get(LoreEntry, lore_id)
    if lore is None or lore.series_id != series_id:
        raise InvalidError("Unknown lore entry for this series", field="lore_entry_id")
    if lore.book_id is not None and lore.book_id != book_id:
        raise InvalidError("Link to shared lore, or lore from the same book", field="lore_entry_id")


def create_entity(session: Session, kind: EntityKind, series_id: str, data: BaseModel) -> Any:
    require(session, Series, series_id)
    book_id = getattr(data, "book_id", None)
    _check_book(session, series_id, book_id)
    _check_lore_link(session, series_id, book_id, getattr(data, "lore_entry_id", None))
    name = data.name  # type: ignore[attr-defined]
    obj = kind.model(
        series_id=series_id,
        book_id=book_id,
        key=assign_key(session, kind.model, data.key, name, series_id=series_id),  # type: ignore[attr-defined]
        name=name,
        **_dump(kind, data, partial=False),
    )
    session.add(obj)
    session.flush()
    if kind.source_type:
        refs.reindex(session, kind.source_type, obj)
    # Refs that mentioned this key before it existed can now resolve.
    _refresh_targeting(session, kind, obj.series_id, obj.key)
    return obj


def update_entity(session: Session, kind: EntityKind, entity_id: str, data: BaseModel) -> Any:
    obj = require(session, kind.model, entity_id)
    changes = data.model_dump(exclude_unset=True)
    old_key = obj.key
    name = changes.get("name")
    if (
        name is not None
        and name != obj.name
        and changes.get("key") is None
        and key_follows_title(obj.key, obj.name, kind.model.__tablename__)
    ):
        obj.key = assign_key(
            session, kind.model, None, name, exclude_id=obj.id, series_id=obj.series_id
        )
    if changes.get("key") is not None:
        obj.key = assign_key(
            session,
            kind.model,
            changes["key"],
            obj.name,
            exclude_id=obj.id,
            series_id=obj.series_id,
        )
    if "book_id" in changes:
        _check_book(session, obj.series_id, changes["book_id"])
        obj.book_id = changes["book_id"]
    if changes.get("name") is not None:
        obj.name = changes["name"]
    if "lore_entry_id" in changes or "book_id" in changes:
        _check_lore_link(
            session,
            obj.series_id,
            obj.book_id,
            getattr(obj, "lore_entry_id", None)
            if "lore_entry_id" not in changes
            else changes["lore_entry_id"],
        )
    for field, value in _dump(kind, data, partial=True).items():
        setattr(obj, field, value)
    session.flush()
    if kind.source_type:
        refs.reindex(session, kind.source_type, obj)
    if obj.key != old_key:
        refs.rename_key(session, obj.series_id, kind.name, old_key, obj.key)
    return obj


def delete_entity(
    session: Session, kind: EntityKind, entity_id: str, *, force: bool = False
) -> None:
    obj = require(session, kind.model, entity_id)
    used = [
        r
        for r, _ in refs.where_used(session, obj.series_id, kind.name, obj.key)
        if not (r.source_type == kind.source_type and r.source_id == obj.id)
    ]
    if used and not force:
        raise ConflictError(
            f"{obj.name} is used in {len(used)} place(s); delete with force to remove anyway",
            ref_count=len(used),
        )
    series_id, key = obj.series_id, obj.key
    if kind.source_type:
        refs.drop(session, kind.source_type, [obj.id])
    if kind.name in ("character", "enemy", "item", "lore"):
        refs.drop_placements(session, f"{kind.name}_id", [obj.id])
    session.delete(obj)
    session.flush()
    session.expire_all()
    _refresh_targeting(session, kind, series_id, key)


def _refresh_targeting(session: Session, kind: EntityKind, series_id: str, key: str) -> None:
    """Reindex sources whose references to ``key`` may resolve differently now."""
    models = refs.SOURCE_MODELS
    sources = {
        (r.source_type, r.source_id) for r, _ in refs.where_used(session, series_id, kind.name, key)
    }
    ctx = refs.RefContext(session, series_id)
    for source_type, source_id in sources:
        src = session.get(models[source_type], source_id)
        if src is not None:
            refs.reindex(session, source_type, src, ctx)  # type: ignore[arg-type]
