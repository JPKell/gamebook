"""FastAPI dependencies."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from gamebook.config import Settings
from gamebook.db.session import Database


def get_database(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(db: Annotated[Database, Depends(get_database)]) -> Iterator[Session]:
    """Unit of work around the path operation.

    Used with ``scope="function"`` so the commit happens *before* the response
    is sent. (FastAPI's default runs yield-dependency teardown after sending,
    which let clients read stale data right after a write, and would report
    success for a write whose commit then failed.)
    """
    with db.session() as session:
        yield session


DatabaseDep = Annotated[Database, Depends(get_database)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[Session, Depends(get_session, scope="function")]
