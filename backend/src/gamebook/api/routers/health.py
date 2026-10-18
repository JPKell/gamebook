"""Liveness / readiness and build metadata."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from gamebook import __version__
from gamebook.api.deps import DatabaseDep

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: Literal["ok", "unavailable"]


@router.get("/health", response_model=HealthResponse)
def get_health(db: DatabaseDep) -> HealthResponse:
    db_ok = db.ping()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=__version__,
        database="ok" if db_ok else "unavailable",
    )
