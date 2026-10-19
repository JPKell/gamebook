"""Export/import use-cases (wraps gamebook.export.tree)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.db.models import Series
from gamebook.export import tree
from gamebook.services.assets import Store, import_blob
from gamebook.services.common import require
from gamebook.services.errors import ConflictError, InvalidError


def _blobs(session: Session, store: Store, series_id: str) -> dict[str, bytes]:
    """The library's image files (missing files are left out; the export stays usable)."""
    out = {}
    for rel, sha, ext in tree.asset_blobs(session, series_id):
        path = store.path(sha, ext)
        if path.is_file():
            out[rel] = path.read_bytes()
    return out


def export_zip(session: Session, store: Store, series_id: str) -> tuple[str, bytes]:
    series = require(session, Series, series_id)
    files = tree.export_series(session, series_id)
    return f"{series.key}.zip", tree.to_zip(files, _blobs(session, store, series_id))


def export_to_dir(session: Session, store: Store, series_key: str, root: Path) -> int:
    series = session.scalar(select(Series).where(Series.key == series_key))
    if series is None:
        raise InvalidError(f"No series with key {series_key!r}")
    files = tree.export_series(session, series.id)
    blobs = _blobs(session, store, series.id)
    tree.write_tree(files, root, blobs)
    return len(files) + len(blobs)


def _writer(store: Store) -> tree.BlobWriter:
    def write(sha: str, ext: str, data: bytes | None) -> tuple[str, int, int] | None:
        p = import_blob(store, sha, ext, data)
        return (p.mime, p.width_px, p.height_px) if p else None

    return write


def _import(
    session: Session, store: Store, files: dict[str, str], blobs: dict[str, bytes], replace: bool
) -> Series:
    try:
        return tree.import_series(
            session, files, replace=replace, blobs=blobs, write_blob=_writer(store)
        )
    except tree.TreeError as exc:
        if "already exists" in str(exc) or "already uses" in str(exc):
            raise ConflictError(str(exc)) from exc
        raise InvalidError(str(exc)) from exc


def import_zip(session: Session, store: Store, data: bytes, *, replace: bool = False) -> Series:
    try:
        files, blobs = tree.from_zip_all(data)
    except Exception as exc:
        raise InvalidError(f"Not a valid export zip: {exc}") from exc
    return _import(session, store, files, blobs, replace)


def import_from_dir(session: Session, store: Store, root: Path, *, replace: bool = False) -> Series:
    try:
        files = tree.read_tree(root)
        blobs = tree.read_blobs(root)
    except tree.TreeError as exc:
        raise InvalidError(str(exc)) from exc
    return _import(session, store, files, blobs, replace)
