"""Editor tooling endpoints."""

from fastapi import APIRouter

from gamebook.api.deps import SessionDep
from gamebook.schemas.analysis import GbxCheckIn, GbxCheckOut
from gamebook.services import gbx_tools

router = APIRouter(tags=["tools"])


@router.post("/gbx/check", response_model=GbxCheckOut)
def check_gbx(data: GbxCheckIn, session: SessionDep) -> GbxCheckOut:
    """Check an expression in context; returns diagnostics, English and odds."""
    return gbx_tools.check(session, data)
