"""LLM providers, prompt templates, the call log and costs."""

from fastapi import APIRouter, Query, Response

from gamebook.api.deps import SessionDep
from gamebook.db.models import LlmCall, PromptTemplate
from gamebook.schemas.llm import (
    CostsOut,
    LlmCallDetail,
    LlmCallPage,
    ProviderIn,
    ProviderOut,
    ProviderTestOut,
    ProviderUpdate,
    TemplateIn,
    TemplateOut,
    TemplatePreviewIn,
    TemplatePreviewOut,
    WritingSettings,
)
from gamebook.services import llm as svc
from gamebook.services import writing
from gamebook.services.common import require

router = APIRouter(tags=["llm"])


@router.get("/llm/providers", response_model=list[ProviderOut])
def list_providers(session: SessionDep) -> list[ProviderOut]:
    return svc.list_providers(session)


@router.post("/llm/providers", response_model=ProviderOut, status_code=201)
def create_provider(data: ProviderIn, session: SessionDep) -> ProviderOut:
    return svc.provider_out(svc.create_provider(session, data))


@router.patch("/llm/providers/{provider_id}", response_model=ProviderOut)
def update_provider(provider_id: str, data: ProviderUpdate, session: SessionDep) -> ProviderOut:
    return svc.provider_out(svc.update_provider(session, provider_id, data))


@router.delete("/llm/providers/{provider_id}", status_code=204)
def delete_provider(provider_id: str, session: SessionDep) -> Response:
    svc.delete_provider(session, provider_id)
    return Response(status_code=204)


@router.post("/llm/providers/{provider_id}/test", response_model=ProviderTestOut)
def test_provider(provider_id: str, session: SessionDep) -> ProviderTestOut:
    """Connect and list the provider's models."""
    return svc.test_provider(session, provider_id)


@router.get("/llm/templates", response_model=list[TemplateOut])
def list_templates(session: SessionDep, role: str | None = None) -> list[PromptTemplate]:
    return svc.list_templates(session, role)


@router.post("/llm/templates/{role}", response_model=TemplateOut, status_code=201)
def save_template(role: str, data: TemplateIn, session: SessionDep) -> PromptTemplate:
    """Save a new version of a role's template and make it active."""
    return svc.save_template(session, role, data)


@router.post("/llm/templates/{template_id}/activate", response_model=TemplateOut)
def activate_template(template_id: str, session: SessionDep) -> PromptTemplate:
    return svc.activate_template(session, template_id)


@router.post("/llm/templates/{role}/preview", response_model=TemplatePreviewOut)
def preview_template(role: str, data: TemplatePreviewIn, session: SessionDep) -> TemplatePreviewOut:
    """Render a template (the active one, or the given text) against a real node's context."""
    return svc.preview_template(session, role, data, writing.context(session, data.variant_id).ctx)


@router.get("/llm/calls", response_model=LlmCallPage)
def list_calls(
    session: SessionDep,
    series_id: str | None = None,
    node_id: str | None = None,
    role: str | None = None,
    status: str | None = None,
    pipeline_run_id: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
) -> LlmCallPage:
    return svc.list_calls(
        session,
        series_id=series_id,
        node_id=node_id,
        role=role,
        status=status,
        pipeline_run_id=pipeline_run_id,
        offset=offset,
        limit=limit,
    )


@router.get("/llm/calls/{call_id}", response_model=LlmCallDetail)
def get_call(call_id: str, session: SessionDep) -> LlmCall:
    return require(session, LlmCall, call_id)


@router.get("/llm/costs", response_model=CostsOut)
def get_costs(session: SessionDep, series_id: str | None = None) -> CostsOut:
    return svc.costs(session, series_id)


@router.get("/series/{series_id}/writing-settings", response_model=WritingSettings)
def get_writing_settings(series_id: str, session: SessionDep) -> WritingSettings:
    return svc.writing_settings(session, series_id)


@router.put("/series/{series_id}/writing-settings", response_model=WritingSettings)
def put_writing_settings(
    series_id: str, data: WritingSettings, session: SessionDep
) -> WritingSettings:
    return svc.save_writing_settings(session, series_id, data)
