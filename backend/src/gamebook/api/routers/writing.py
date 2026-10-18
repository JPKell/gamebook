"""Prose versions, review, the writing queue and generation jobs."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from gamebook.api.deps import SessionDep
from gamebook.api.routers.playtest import RunnerDep
from gamebook.db.models import Job, PipelineRun, ProseVersion
from gamebook.schemas.playtest import JobOut
from gamebook.schemas.writing import (
    ActGenerateIn,
    ApproveIn,
    ContextOut,
    GenerateIn,
    NodeProse,
    PipelineRunOut,
    ProseCreate,
    ProseOut,
    QueueOut,
    RejectIn,
)
from gamebook.services import writing as svc

router = APIRouter(tags=["writing"])


class SummaryIn(BaseModel):
    summary: str = Field(max_length=2000)


@router.get("/books/{book_id}/writing-queue", response_model=QueueOut)
def get_queue(book_id: str, session: SessionDep) -> QueueOut:
    """Every text variant in canonical order with its prose status."""
    return svc.queue(session, book_id)


@router.get("/nodes/{node_id}/prose", response_model=NodeProse)
def get_node_prose(node_id: str, session: SessionDep) -> NodeProse:
    return svc.node_prose(session, node_id)


@router.get("/variants/{variant_id}/context", response_model=ContextOut)
def get_context(variant_id: str, session: SessionDep) -> ContextOut:
    """What the writer will see for this variant, with token estimates."""
    return svc.context(session, variant_id)


@router.post("/variants/{variant_id}/prose", response_model=ProseOut, status_code=201)
def write_prose(variant_id: str, data: ProseCreate, session: SessionDep) -> ProseVersion:
    return svc.write_prose(session, variant_id, data)


@router.post("/prose/{prose_id}/approve", response_model=ProseOut)
def approve(prose_id: str, data: ApproveIn, session: SessionDep) -> ProseVersion:
    return svc.approve(session, prose_id, data)


@router.post("/prose/{prose_id}/reject", response_model=ProseOut)
def reject(prose_id: str, data: RejectIn, session: SessionDep) -> ProseVersion:
    return svc.reject(session, prose_id, data)


@router.put("/prose/{prose_id}/summary", response_model=ProseOut)
def put_summary(prose_id: str, data: SummaryIn, session: SessionDep) -> ProseVersion:
    return svc.update_summary(session, prose_id, data.summary)


@router.post("/variants/{variant_id}/generate", response_model=JobOut, status_code=201)
def generate(variant_id: str, data: GenerateIn, session: SessionDep, runner: RunnerDep) -> Job:
    """Run writer → critic → editor for one variant (a background job)."""
    return svc.start_variant(session, runner, variant_id, data)


@router.post("/acts/{act_id}/generate", response_model=JobOut, status_code=201)
def generate_act(act_id: str, data: ActGenerateIn, session: SessionDep, runner: RunnerDep) -> Job:
    """Write an act's sections in canonical order (a background job)."""
    return svc.start_act(session, runner, act_id, data)


@router.get("/pipeline-runs/{run_id}", response_model=PipelineRunOut)
def get_run(run_id: str, session: SessionDep) -> PipelineRun:
    return svc.pipeline_run(session, run_id)
