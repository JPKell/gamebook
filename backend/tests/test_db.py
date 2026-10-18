from pathlib import Path

import pytest
from sqlalchemy import String, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from gamebook.db import Database, IdMixin, Repository, TimestampMixin, migrate
from gamebook.db.repository import NotFoundError


class _TestBase(DeclarativeBase):
    pass


class Widget(IdMixin, TimestampMixin, _TestBase):
    __tablename__ = "widget"
    name: Mapped[str] = mapped_column(String(50))


class WidgetRepo(Repository[Widget]):
    model = Widget


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(f"sqlite:///{tmp_path / 'nested' / 'test.db'}")
    _TestBase.metadata.create_all(database.engine)
    return database


def test_sqlite_pragmas(db: Database) -> None:
    with db.engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"


def test_repository_crud_and_mixins(db: Database) -> None:
    with db.session() as s:
        repo = WidgetRepo(s)
        w = repo.add(Widget(name="a"))
        repo.add(Widget(name="b"))
        assert len(w.id) == 36
        assert w.created_at is not None
        wid = w.id
    with db.session() as s:
        repo = WidgetRepo(s)
        assert repo.count() == 2
        assert [x.name for x in repo.list(limit=1)] == ["a"]
        repo.delete(repo.require(wid))
    with db.session() as s:
        repo = WidgetRepo(s)
        assert repo.get(wid) is None
        with pytest.raises(NotFoundError):
            repo.require(wid)


def test_unit_of_work_rolls_back(db: Database) -> None:
    def add_then_fail() -> None:
        with db.session() as s:
            WidgetRepo(s).add(Widget(name="x"))
            raise RuntimeError

    with pytest.raises(RuntimeError):
        add_then_fail()
    with db.session() as s:
        assert WidgetRepo(s).count() == 0


def test_ping(db: Database, tmp_path: Path) -> None:
    assert db.ping()


def test_migrate_upgrade_head(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'm.db'}"
    migrate.upgrade(url)
    migrate.upgrade(url)  # idempotent
    db = Database(url)
    assert "alembic_version" in inspect(db.engine).get_table_names()


def test_models_match_migrations(tmp_path: Path) -> None:
    """Autogenerate must find nothing to do: models and migrations agree."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    import gamebook.db.models  # noqa: F401
    from gamebook.db.base import Base

    url = f"sqlite:///{tmp_path / 'c.db'}"
    migrate.upgrade(url)
    with Database(url).engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_migrations_downgrade_and_reapply(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'd.db'}"
    migrate.upgrade(url)
    migrate.downgrade(url, "base")
    tables = set(inspect(Database(url).engine).get_table_names())
    assert tables <= {"alembic_version"}
    migrate.upgrade(url)
    assert "node" in inspect(Database(url).engine).get_table_names()
