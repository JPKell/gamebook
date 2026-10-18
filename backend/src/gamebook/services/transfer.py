"""Export/import use-cases (wraps gamebook.export.tree)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.db.models import Series
from gamebook.export import tree
from gamebook.services.common import require
from gamebook.services.errors import ConflictError, InvalidError


def export_zip(session: Session, series_id: str) -> tuple[str, bytes]:
    series = require(session, Series, series_id)
    return f"{series.key}.zip", tree.to_zip(tree.export_series(session, series_id))


def export_to_dir(session: Session, series_key: str, root: Path) -> int:
    series = session.scalar(select(Series).where(Series.key == series_key))
    if series is None:
        raise InvalidError(f"No series with key {series_key!r}")
    files = tree.export_series(session, series.id)
    tree.write_tree(files, root)
    return len(files)


def _import(session: Session, files: dict[str, str], replace: bool) -> Series:
    try:
        return tree.import_series(session, files, replace=replace)
    except tree.TreeError as exc:
        if "already exists" in str(exc) or "already uses" in str(exc):
            raise ConflictError(str(exc)) from exc
        raise InvalidError(str(exc)) from exc


def import_zip(session: Session, data: bytes, *, replace: bool = False) -> Series:
    try:
        files = tree.from_zip(data)
    except Exception as exc:
        raise InvalidError(f"Not a valid export zip: {exc}") from exc
    return _import(session, files, replace)


def import_from_dir(session: Session, root: Path, *, replace: bool = False) -> Series:
    try:
        files = tree.read_tree(root)
    except tree.TreeError as exc:
        raise InvalidError(str(exc)) from exc
    return _import(session, files, replace)
