"""Providers, prompt templates, logged model calls and cost reporting."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gamebook.db.models import LlmCall, LlmProvider, PromptTemplate, Series
from gamebook.db.session import Database
from gamebook.llm import templates
from gamebook.llm.client import ChatClient, LlmError, Message, ProviderConfig, client_for
from gamebook.llm.jsonparse import BadJson, parse_object
from gamebook.schemas.llm import (
    CostRow,
    CostsOut,
    LlmCallPage,
    ProviderIn,
    ProviderOut,
    ProviderTestOut,
    ProviderUpdate,
    RoleModel,
    TemplateIn,
    TemplatePreviewIn,
    TemplatePreviewOut,
    WritingSettings,
)
from gamebook.services.common import require
from gamebook.services.errors import ConflictError, InvalidError

# ── providers ────────────────────────────────────────────────────────────


#: Shown instead of header values that look secret (and kept when sent back).
MASK = "********"
_SECRET_HEADER = ("auth", "key", "token", "secret", "cookie", "password")


def _secret(name: str) -> bool:
    return any(word in name.lower() for word in _SECRET_HEADER)


def provider_out(p: LlmProvider) -> ProviderOut:
    return ProviderOut.model_validate(
        {
            **{k: getattr(p, k) for k in ProviderOut.model_fields if hasattr(p, k)},
            "headers": {k: (MASK if _secret(k) else v) for k, v in (p.headers or {}).items()},
            "api_key_present": bool(p.api_key_env and os.environ.get(p.api_key_env)),
        }
    )


def list_providers(session: Session) -> list[ProviderOut]:
    return [
        provider_out(p) for p in session.scalars(select(LlmProvider).order_by(LlmProvider.name))
    ]


def create_provider(session: Session, data: ProviderIn) -> LlmProvider:
    if data.kind == "openai" and not data.base_url:
        raise InvalidError("An OpenAI-compatible provider needs a base URL", field="base_url")
    p = LlmProvider(**data.model_dump(mode="json"))
    session.add(p)
    session.flush()
    return p


def update_provider(session: Session, provider_id: str, data: ProviderUpdate) -> LlmProvider:
    p = require(session, LlmProvider, provider_id)
    for k, v in data.model_dump(exclude_unset=True, mode="json").items():
        if v is None and k != "api_key_env":
            continue
        if k == "headers":
            # A masked value sent back means "keep what's stored".
            v = {
                name: (p.headers or {}).get(name, "") if val == MASK else val
                for name, val in v.items()
            }
        setattr(p, k, v)
    session.flush()
    return p


def delete_provider(session: Session, provider_id: str) -> None:
    p = require(session, LlmProvider, provider_id)
    for s in session.scalars(select(Series)):
        roles = (s.writing or {}).get("roles", {})
        if any((r or {}).get("provider_id") == provider_id for r in roles.values()):
            raise ConflictError(f"Series '{s.title}' uses {p.name} in its writing settings")
    session.delete(p)


def config(p: LlmProvider) -> ProviderConfig:
    return ProviderConfig(
        id=p.id,
        kind=p.kind,
        base_url=p.base_url,
        api_key_env=p.api_key_env,
        max_concurrency=p.max_concurrency,
        timeout_s=p.timeout_s,
        headers=dict(p.headers),
    )


def test_provider(session: Session, provider_id: str) -> ProviderTestOut:
    p = require(session, LlmProvider, provider_id)
    started = time.monotonic()
    try:
        client = client_for(config(p))
        models = client.list_models() if hasattr(client, "list_models") else []
    except (LlmError, OSError) as exc:
        return ProviderTestOut(ok=False, message=str(exc))
    except Exception as exc:  # network stacks raise many things; report, don't 500
        return ProviderTestOut(ok=False, message=f"{type(exc).__name__}: {exc}")
    ms = int((time.monotonic() - started) * 1000)
    return ProviderTestOut(
        ok=True,
        message=f"Connected; {len(models)} model(s) listed" if models else "Connected",
        models=models[:500],
        latency_ms=ms,
    )


# ── templates ────────────────────────────────────────────────────────────


def ensure_templates(session: Session) -> None:
    """Seed version 1 of every role from the built-in defaults."""
    have = set(session.scalars(select(PromptTemplate.role).distinct()))
    for role in templates.ROLES:
        if role not in have:
            system, user = templates.DEFAULTS[role]
            session.add(
                PromptTemplate(
                    role=role,
                    version=1,
                    system=system,
                    user=user,
                    notes="Built-in default",
                    is_active=True,
                )
            )
    session.flush()


def active_template(session: Session, role: str) -> PromptTemplate:
    ensure_templates(session)
    t = session.scalar(
        select(PromptTemplate).where(PromptTemplate.role == role, PromptTemplate.is_active)
    )
    if t is None:
        raise InvalidError(f"No active template for {role}")
    return t


def list_templates(session: Session, role: str | None = None) -> list[PromptTemplate]:
    ensure_templates(session)
    q = select(PromptTemplate).order_by(PromptTemplate.role, PromptTemplate.version.desc())
    if role:
        q = q.where(PromptTemplate.role == role)
    return list(session.scalars(q))


def save_template(session: Session, role: str, data: TemplateIn) -> PromptTemplate:
    if role not in templates.ROLES:
        raise InvalidError(f"Unknown role {role!r}", field="role")
    for name, src in (("system", data.system), ("user", data.user)):
        error = templates.check(src)
        if error:
            raise InvalidError(f"Template error in the {name} prompt: {error}", field=name)
    ensure_templates(session)
    latest = session.scalar(
        select(func.max(PromptTemplate.version)).where(PromptTemplate.role == role)
    )
    for t in session.scalars(select(PromptTemplate).where(PromptTemplate.role == role)):
        t.is_active = False
    t = PromptTemplate(
        role=role,
        version=(latest or 0) + 1,
        system=data.system,
        user=data.user,
        notes=data.notes,
        is_active=True,
    )
    session.add(t)
    session.flush()
    return t


def activate_template(session: Session, template_id: str) -> PromptTemplate:
    t = require(session, PromptTemplate, template_id)
    for other in session.scalars(select(PromptTemplate).where(PromptTemplate.role == t.role)):
        other.is_active = other.id == t.id
    session.flush()
    return t


def preview_template(
    session: Session, role: str, data: TemplatePreviewIn, ctx: dict[str, Any]
) -> TemplatePreviewOut:
    active = active_template(session, role)
    variables = {
        "ctx": ctx,
        "notes": "",
        "draft": "(the draft goes here)",
        "issues": [{"quote": "...", "problem": "(an issue)", "suggestion": "(a fix)"}],
        "text": "(the text to summarise goes here)",
    }
    try:
        system = templates.render(
            data.system if data.system is not None else active.system, **variables
        )
        user = templates.render(data.user if data.user is not None else active.user, **variables)
    except Exception as exc:  # jinja reports many error types; show them, don't 500
        return TemplatePreviewOut(system="", user="", tokens=0, error=str(exc))
    return TemplatePreviewOut(system=system, user=user, tokens=(len(system) + len(user)) // 4)


# ── writing settings ─────────────────────────────────────────────────────


def writing_settings(session: Session, series_id: str) -> WritingSettings:
    s = require(session, Series, series_id)
    return WritingSettings.model_validate(s.writing or {})


def save_writing_settings(
    session: Session, series_id: str, data: WritingSettings
) -> WritingSettings:
    s = require(session, Series, series_id)
    for role, rm in data.roles.items():
        if rm.provider_id is not None:
            p = session.get(LlmProvider, rm.provider_id)
            if p is None:
                raise InvalidError(f"{role}: unknown provider", field=f"roles.{role}")
    s.writing = data.model_dump(mode="json")
    session.flush()
    return data


# ── calls ────────────────────────────────────────────────────────────────


@dataclass
class CallScope:
    """Where a call belongs, for the log."""

    series_id: str | None = None
    book_id: str | None = None
    node_id: str | None = None
    job_id: str | None = None
    pipeline_run_id: str | None = None


@dataclass
class CallResult:
    text: str
    call_id: str
    cost_usd: float


def _model_info(p: LlmProvider, model: str) -> dict[str, Any]:
    return next((m for m in p.models if m.get("id") == model), {})


def resolve_role(
    session: Session, settings: WritingSettings, role: str
) -> tuple[LlmProvider, RoleModel]:
    """The provider and model for a role.

    A role without its own provider and model uses the writer's, keeping its own
    temperature and max tokens when those were set.
    """
    own = settings.roles.get(role)  # type: ignore[call-overload]
    writer = settings.roles.get("writer")
    rm = own
    if rm is None or rm.provider_id is None or not rm.model:
        if writer is None:
            rm = None
        elif own is None:
            rm = writer
        else:
            rm = own.model_copy(update={"provider_id": writer.provider_id, "model": writer.model})
    if rm is None or rm.provider_id is None or not rm.model:
        raise InvalidError(
            f"No model is set for the {role}. Choose one in Writing → Pipeline settings."
        )
    p = session.get(LlmProvider, rm.provider_id)
    if p is None or not p.enabled:
        raise InvalidError(f"The {role}'s provider is missing or disabled")
    return p, rm


#: Tests can swap the client factory (e.g. to inject failures).
CLIENT_FACTORY = client_for


def call(
    db: Database,
    *,
    role: str,
    variables: dict[str, Any],
    settings: WritingSettings,
    scope: CallScope,
    json_schema: dict[str, Any] | None = None,
    client: ChatClient | None = None,
    nudge: str | None = None,
    previous: str | None = None,
) -> CallResult:
    """Render the role's active template, call the model, log it. Raises LlmError on failure."""
    with db.session() as s:
        provider, rm = resolve_role(s, settings, role)
        tpl = active_template(s, role)
        pcfg = config(provider)
        info = _model_info(provider, rm.model or "")
        tpl_id, tpl_version = tpl.id, tpl.version
        try:
            messages: list[Message] = [
                {"role": "system", "content": templates.render(tpl.system, **variables)},
                {"role": "user", "content": templates.render(tpl.user, **variables)},
            ]
        except Exception as exc:  # jinja errors: a broken edited template
            raise LlmError(f"The {role} template failed to render: {exc}") from exc
        if previous is not None:
            messages.append({"role": "assistant", "content": previous})
        if nudge:
            messages.append({"role": "user", "content": nudge})
    model = rm.model or ""
    status, error, text = "ok", None, ""
    prompt_tokens = completion_tokens = latency = 0
    owned = client is None
    chat = client or CLIENT_FACTORY(pcfg)
    try:
        completion = chat.complete(
            model,
            messages,
            role=role,
            temperature=rm.temperature,
            max_tokens=rm.max_tokens,
            json_schema=json_schema,
        )
        text = completion.text
        prompt_tokens, completion_tokens = completion.prompt_tokens, completion.completion_tokens
        latency = completion.latency_ms
    except LlmError as exc:
        status, error = "error", str(exc)
    finally:
        if owned and hasattr(chat, "close"):
            chat.close()
    cost = (
        prompt_tokens * float(info.get("input_per_mtok", 0) or 0)
        + completion_tokens * float(info.get("output_per_mtok", 0) or 0)
    ) / 1_000_000
    with db.session() as s:
        row = LlmCall(
            role=role,
            template_id=tpl_id,
            template_version=tpl_version,
            provider_id=pcfg.id,
            model=model,
            messages=messages,
            response=text,
            status=status,
            error=error,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency,
            cost_usd=round(cost, 6),
            series_id=scope.series_id,
            book_id=scope.book_id,
            node_id=scope.node_id,
            job_id=scope.job_id,
            pipeline_run_id=scope.pipeline_run_id,
        )
        s.add(row)
        s.flush()
        call_id = row.id
    if error is not None:
        raise LlmError(error, cost_usd=cost)
    return CallResult(text=text.strip(), call_id=call_id, cost_usd=cost)


def call_json(db: Database, **kw: Any) -> tuple[dict[str, Any], CallResult]:
    """``call`` expecting a JSON object; re-asks once if the reply isn't valid JSON.

    The returned result's cost covers both calls when a retry was needed.
    """
    first = call(db, **kw)
    try:
        return parse_object(first.text), first
    except BadJson:
        pass
    # Overrides the caller's own previous/nudge (e.g. a re-ask of its own).
    retry = call(
        db,
        **{
            **kw,
            "previous": first.text,
            "nudge": "Your previous reply was not valid JSON. Reply with only the JSON object.",
        },
    )
    combined = CallResult(
        text=retry.text, call_id=retry.call_id, cost_usd=first.cost_usd + retry.cost_usd
    )
    try:
        return parse_object(retry.text), combined
    except BadJson as exc:
        raise LlmError(
            f"The {kw['role']} didn't return valid JSON twice: {exc}", cost_usd=combined.cost_usd
        ) from exc


# ── log & costs ──────────────────────────────────────────────────────────


def list_calls(
    session: Session,
    *,
    series_id: str | None,
    node_id: str | None,
    role: str | None,
    status: str | None,
    pipeline_run_id: str | None,
    offset: int,
    limit: int,
) -> LlmCallPage:
    from gamebook.schemas.llm import LlmCallOut

    q = select(LlmCall)
    for col, value in (
        (LlmCall.series_id, series_id),
        (LlmCall.node_id, node_id),
        (LlmCall.role, role),
        (LlmCall.status, status),
        (LlmCall.pipeline_run_id, pipeline_run_id),
    ):
        if value:
            q = q.where(col == value)
    total = session.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = session.scalars(q.order_by(LlmCall.created_at.desc()).offset(offset).limit(limit))
    return LlmCallPage(total=total, calls=[LlmCallOut.model_validate(r) for r in rows])


def costs(session: Session, series_id: str | None) -> CostsOut:
    q = select(LlmCall)
    if series_id:
        q = q.where(LlmCall.series_id == series_id)
    groups: dict[str, dict[str, list[float]]] = {
        "role": defaultdict(lambda: [0, 0, 0, 0.0]),
        "model": defaultdict(lambda: [0, 0, 0, 0.0]),
        "day": defaultdict(lambda: [0, 0, 0, 0.0]),
    }
    total = 0.0
    for c in session.scalars(q):
        total += c.cost_usd
        for name, key in (
            ("role", c.role),
            ("model", c.model),
            ("day", c.created_at.date().isoformat()),
        ):
            g = groups[name][key]
            g[0] += 1
            g[1] += c.prompt_tokens
            g[2] += c.completion_tokens
            g[3] += c.cost_usd

    def rows(name: str) -> list[CostRow]:
        return [
            CostRow(
                key=k,
                calls=int(v[0]),
                prompt_tokens=int(v[1]),
                completion_tokens=int(v[2]),
                cost_usd=round(v[3], 6),
            )
            for k, v in sorted(groups[name].items())
        ]

    return CostsOut(
        total_usd=round(total, 6), by_role=rows("role"), by_model=rows("model"), by_day=rows("day")
    )
