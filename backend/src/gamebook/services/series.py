"""Series and rule-system use-cases."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from gamebook.core.rules import default_rule_system
from gamebook.db.models import Book, RuleSystem, Series
from gamebook.schemas.series import (
    RuleSystemCreate,
    RuleSystemUpdate,
    SeriesCreate,
    SeriesUpdate,
)
from gamebook.services import refs
from gamebook.services.common import assign_key, require


def list_series(session: Session) -> list[Series]:
    return list(session.scalars(select(Series).order_by(Series.title)))


def create_series(session: Session, data: SeriesCreate) -> Series:
    series = Series(
        key=assign_key(session, Series, data.key, data.title),
        title=data.title,
        description=data.description,
        style=data.style.model_dump(),
    )
    session.add(series)
    session.flush()
    session.add(
        RuleSystem(
            series_id=series.id,
            key="standard",
            name="Standard rules",
            is_active=True,
            definition=default_rule_system().model_dump(mode="json"),
        )
    )
    session.flush()
    return series


def update_series(session: Session, series_id: str, data: SeriesUpdate) -> Series:
    series = require(session, Series, series_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("key") is not None:
        series.key = assign_key(session, Series, data.key, series.title, exclude_id=series.id)
    for field in ("title", "description"):
        if changes.get(field) is not None:
            setattr(series, field, changes[field])
    if data.style is not None:
        series.style = data.style.model_dump()
    session.flush()
    return series


def delete_series(session: Session, series_id: str) -> None:
    series = require(session, Series, series_id)
    # Break the book ↔ start-node cycle before cascading.
    session.execute(update(Book).where(Book.series_id == series_id).values(start_node_id=None))
    session.delete(series)
    session.flush()


# ── rule systems ─────────────────────────────────────────────────────────


def list_rule_systems(session: Session, series_id: str) -> list[RuleSystem]:
    require(session, Series, series_id)
    return list(
        session.scalars(
            select(RuleSystem).where(RuleSystem.series_id == series_id).order_by(RuleSystem.name)
        )
    )


def _activate(session: Session, rs: RuleSystem) -> None:
    session.execute(
        update(RuleSystem)
        .where(RuleSystem.series_id == rs.series_id, RuleSystem.id != rs.id)
        .values(is_active=False)
    )
    rs.is_active = True


def create_rule_system(session: Session, series_id: str, data: RuleSystemCreate) -> RuleSystem:
    require(session, Series, series_id)
    definition = data.definition or default_rule_system()
    rs = RuleSystem(
        series_id=series_id,
        key=assign_key(session, RuleSystem, data.key, data.name, series_id=series_id),
        name=data.name,
        is_active=False,
        definition=definition.model_dump(mode="json"),
    )
    session.add(rs)
    session.flush()
    if data.is_active:
        _activate(session, rs)
        session.flush()
        refs.rebuild_series(session, series_id)
    session.flush()
    return rs


def update_rule_system(session: Session, rs_id: str, data: RuleSystemUpdate) -> RuleSystem:
    rs = require(session, RuleSystem, rs_id)
    if data.key is not None:
        rs.key = assign_key(
            session, RuleSystem, data.key, rs.name, exclude_id=rs.id, series_id=rs.series_id
        )
    if data.name is not None:
        rs.name = data.name
    if data.definition is not None:
        rs.definition = data.definition.model_dump(mode="json")
    if data.is_active:
        _activate(session, rs)
    elif data.is_active is False:
        rs.is_active = False
    session.flush()
    # Reference classification depends on the active tiers.
    refs.rebuild_series(session, rs.series_id)
    return rs


def delete_rule_system(session: Session, rs_id: str) -> None:
    rs = require(session, RuleSystem, rs_id)
    series_id, was_active = rs.series_id, rs.is_active
    session.delete(rs)
    session.flush()
    if was_active:
        refs.rebuild_series(session, series_id)
