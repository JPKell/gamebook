"""Act outlines (story beats) and the state digest."""

from fastapi import APIRouter, Query, Response

from gamebook.api.deps import SessionDep
from gamebook.db.models import StoryBeat
from gamebook.schemas.common import Reorder
from gamebook.schemas.outline import (
    BeatCreate,
    BeatOut,
    BeatUpdate,
    BookDigestOut,
    NodeDigestOut,
    OutlineOut,
)
from gamebook.services import outline as svc

router = APIRouter(tags=["outline"])


@router.get("/books/{book_id}/outline", response_model=OutlineOut)
def get_outline(book_id: str, session: SessionDep) -> OutlineOut:
    """Acts with their summaries and story beats."""
    return svc.outline(session, book_id)


@router.post("/acts/{act_id}/beats", response_model=BeatOut, status_code=201)
def create_beat(act_id: str, data: BeatCreate, session: SessionDep) -> StoryBeat:
    return svc.create_beat(session, act_id, data)


@router.patch("/beats/{beat_id}", response_model=BeatOut)
def update_beat(beat_id: str, data: BeatUpdate, session: SessionDep) -> StoryBeat:
    return svc.update_beat(session, beat_id, data)


@router.delete("/beats/{beat_id}", status_code=204)
def delete_beat(beat_id: str, session: SessionDep) -> Response:
    svc.delete_beat(session, beat_id)
    return Response(status_code=204)


@router.put("/acts/{act_id}/beats/order", response_model=list[BeatOut])
def reorder_beats(act_id: str, data: Reorder, session: SessionDep) -> list[StoryBeat]:
    return svc.reorder_beats(session, act_id, data)


@router.get("/books/{book_id}/digest", response_model=BookDigestOut)
def get_book_digest(
    book_id: str, session: SessionDep, tier: str | None = Query(default=None)
) -> BookDigestOut:
    """What readers must / may have at every node (default tier: the highest)."""
    return svc.book_digest(session, book_id, tier)


@router.get("/nodes/{node_id}/digest", response_model=NodeDigestOut)
def get_node_digest(
    node_id: str, session: SessionDep, tier: str | None = Query(default=None)
) -> NodeDigestOut:
    return svc.node_digest(session, node_id, tier)
