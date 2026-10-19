"""LLM authoring assists: consistency checks, suggested sections, lore extraction."""

from typing import Any

from fastapi import APIRouter

from gamebook.api.deps import SessionDep
from gamebook.api.routers.playtest import RunnerDep
from gamebook.db.models import Act, AssistItem, Job, Node
from gamebook.schemas.assist import (
    AcceptLoreIn,
    AcceptSuggestionIn,
    AssistItemOut,
    ConsistencyIn,
    ExtractLoreIn,
    RejectSuggestionIn,
    StatusIn,
    SuggestIn,
)
from gamebook.schemas.playtest import JobOut
from gamebook.services import assist as svc
from gamebook.services.common import require

router = APIRouter(tags=["assist"])


@router.post("/books/{book_id}/consistency", response_model=JobOut, status_code=201)
def check_book_consistency(
    book_id: str, data: ConsistencyIn, session: SessionDep, runner: RunnerDep
) -> Job:
    """Check every section with prose (optionally one act) against lore, digest and mechanics."""
    return svc.start_consistency(session, runner, book_id=book_id, act_id=data.act_id)


@router.post("/nodes/{node_id}/consistency", response_model=JobOut, status_code=201)
def check_node_consistency(node_id: str, session: SessionDep, runner: RunnerDep) -> Job:
    node = require(session, Node, node_id)
    return svc.start_consistency(session, runner, book_id=node.book_id, node_id=node_id)


@router.post("/acts/{act_id}/suggest", response_model=JobOut, status_code=201)
def suggest_sections(act_id: str, data: SuggestIn, session: SessionDep, runner: RunnerDep) -> Job:
    """Propose new sections and choices for an act's uncovered beats (a draft subgraph)."""
    require(session, Act, act_id)
    return svc.start_suggest(session, runner, act_id, data.notes)


@router.post("/books/{book_id}/extract-lore", response_model=JobOut, status_code=201)
def extract_lore(book_id: str, data: ExtractLoreIn, session: SessionDep, runner: RunnerDep) -> Job:
    """Propose new and updated characters and lore from approved prose."""
    return svc.start_extract(session, runner, book_id, data.act_id)


@router.get("/books/{book_id}/assist", response_model=list[AssistItemOut])
def list_assist_items(
    book_id: str,
    session: SessionDep,
    kind: str | None = None,
    status: str | None = None,
    node_id: str | None = None,
) -> list[dict[str, Any]]:
    return svc.list_items(session, book_id, kind, status, node_id)


@router.patch("/assist/{item_id}", response_model=AssistItemOut)
def set_assist_status(item_id: str, data: StatusIn, session: SessionDep) -> AssistItem:
    """Dismiss a finding (or reopen it), or reject a lore draft."""
    return svc.set_status(session, item_id, data.status)


@router.post("/assist/{item_id}/accept-suggestion", response_model=AssistItemOut)
def accept_suggestion(item_id: str, data: AcceptSuggestionIn, session: SessionDep) -> AssistItem:
    return svc.accept_suggestion(session, item_id, data)


@router.post("/assist/{item_id}/reject-suggestion", response_model=AssistItemOut)
def reject_suggestion(item_id: str, data: RejectSuggestionIn, session: SessionDep) -> AssistItem:
    return svc.reject_suggestion(session, item_id, data)


@router.post("/assist/{item_id}/accept-lore", response_model=AssistItemOut)
def accept_lore(item_id: str, data: AcceptLoreIn, session: SessionDep) -> AssistItem:
    return svc.accept_lore(session, item_id, data)
