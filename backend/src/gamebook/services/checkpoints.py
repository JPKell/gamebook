"""Named whole-database checkpoints (SQLite online backup API)."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from gamebook.db.session import Database
from gamebook.services.errors import InvalidError

_NAME_RE = re.compile(r"[^A-Za-z0-9_-]+")


@dataclass(frozen=True)
class Checkpoint:
    id: str
    name: str
    created_at: datetime
    size: int


def _db_path(db: Database) -> Path:
    url = make_url(db.url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise InvalidError("Checkpoints need a file-based SQLite database")
    return Path(url.database)


def _dir(db: Database) -> Path:
    d = _db_path(db).parent / "checkpoints"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse(path: Path) -> Checkpoint:
    stamp, _, slug = path.stem.partition("__")
    created = datetime.strptime(stamp, "%Y%m%dT%H%M%S%f").replace(tzinfo=UTC)
    return Checkpoint(
        id=path.stem, name=slug.replace("-", " "), created_at=created, size=path.stat().st_size
    )


def create(db: Database, name: str) -> Checkpoint:
    slug = _NAME_RE.sub("-", name.strip()).strip("-")[:60] or "checkpoint"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    target = _dir(db) / f"{stamp}__{slug}.db"
    with sqlite3.connect(_db_path(db)) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    return _parse(target)


def list_all(db: Database) -> list[Checkpoint]:
    return sorted(
        (_parse(p) for p in _dir(db).glob("*__*.db")), key=lambda c: c.created_at, reverse=True
    )


def _find(db: Database, checkpoint_id: str) -> Path:
    if "/" in checkpoint_id or "\\" in checkpoint_id or ".." in checkpoint_id:
        raise InvalidError("Bad checkpoint id")
    path = _dir(db) / f"{checkpoint_id}.db"
    if not path.is_file():
        raise InvalidError(f"No checkpoint {checkpoint_id!r}")
    return path


def restore(db: Database, checkpoint_id: str) -> Checkpoint:
    """Replace the live database with a checkpoint. Saves a safety checkpoint first."""
    path = _find(db, checkpoint_id)
    safety = create(db, "before-restore")
    db.engine.dispose()
    with sqlite3.connect(path) as src, sqlite3.connect(_db_path(db)) as dst:
        src.backup(dst)
    db.engine.dispose()
    return safety


def delete(db: Database, checkpoint_id: str) -> None:
    _find(db, checkpoint_id).unlink()
