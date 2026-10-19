"""LLM providers, prompt templates, the call log and writing settings."""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from gamebook.schemas.common import In, Out

ProviderKind = Literal["openai", "fake"]
KEY_ENV_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*_(KEY|TOKEN|key|token)$"
_KEY_ENV_RE = re.compile(KEY_ENV_PATTERN)


def _check_key_env(v: str | None) -> str | None:
    """A variable *name* like LLM_API_KEY — never the key itself."""
    if v is None:
        return v
    v = v.strip()
    if not v:
        return None
    if not _KEY_ENV_RE.match(v):
        raise ValueError(
            "Enter the name of an environment variable that holds the key, ending in _KEY "
            "or _TOKEN (e.g. LLM_API_KEY), not the key itself. Put the key in the server's "
            ".env file as LLM_API_KEY=… and restart."
        )
    return v


Role = Literal[
    "writer",
    "critic",
    "editor",
    "summarizer",
    "consistency",
    "suggester",
    "lore_extractor",
    "player",
]


class ModelInfo(In):
    id: str = Field(min_length=1, max_length=200)
    label: str = ""
    context_window: int = Field(default=8192, ge=512, le=10_000_000)
    #: USD per million tokens
    input_per_mtok: float = Field(default=0.0, ge=0)
    output_per_mtok: float = Field(default=0.0, ge=0)


class ProviderIn(In):
    name: str = Field(min_length=1, max_length=200)
    kind: ProviderKind = "openai"
    base_url: str = Field(default="", max_length=500)
    #: Only variables named like keys or tokens, so a provider can't be pointed at
    #: arbitrary server secrets.
    api_key_env: str | None = Field(default=None, max_length=100)
    models: list[ModelInfo] = Field(default_factory=list, max_length=200)
    max_concurrency: int = Field(default=2, ge=1, le=32)
    timeout_s: float = Field(default=120.0, ge=5, le=1800)
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True

    _key_env = field_validator("api_key_env")(_check_key_env)

    @field_validator("base_url")
    @classmethod
    def _url(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return v


class ProviderUpdate(In):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    base_url: str | None = Field(default=None, max_length=500)
    api_key_env: str | None = Field(default=None, max_length=100)
    models: list[ModelInfo] | None = Field(default=None, max_length=200)
    max_concurrency: int | None = Field(default=None, ge=1, le=32)
    timeout_s: float | None = Field(default=None, ge=5, le=1800)
    headers: dict[str, str] | None = None
    enabled: bool | None = None

    _key_env = field_validator("api_key_env")(_check_key_env)


class ProviderOut(Out):
    id: str
    name: str
    kind: str
    base_url: str
    api_key_env: str | None
    #: Whether the environment variable is set on the server (the key itself is never sent).
    api_key_present: bool
    models: list[dict[str, Any]]
    max_concurrency: int
    timeout_s: float
    headers: dict[str, str]
    enabled: bool


class ProviderTestOut(Out):
    ok: bool
    message: str
    models: list[str] = Field(default_factory=list)
    latency_ms: int | None = None


class TemplateIn(In):
    system: str = Field(max_length=50_000)
    user: str = Field(max_length=50_000)
    notes: str = Field(default="", max_length=2000)


class TemplateOut(Out):
    id: str
    role: str
    version: int
    system: str
    user: str
    notes: str
    is_active: bool
    created_at: datetime


class TemplatePreviewIn(In):
    variant_id: str
    system: str | None = None
    user: str | None = None


class TemplatePreviewOut(Out):
    system: str
    user: str
    tokens: int
    error: str | None = None


class LlmCallOut(Out):
    id: str
    created_at: datetime
    role: str
    template_version: int | None
    provider_id: str | None
    model: str
    status: str
    error: str | None
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    cost_usd: float
    book_id: str | None
    node_id: str | None
    pipeline_run_id: str | None


class LlmCallDetail(LlmCallOut):
    messages: list[dict[str, Any]]
    response: str


class LlmCallPage(Out):
    total: int
    calls: list[LlmCallOut]


class CostRow(Out):
    key: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class CostsOut(Out):
    total_usd: float
    by_role: list[CostRow]
    by_model: list[CostRow]
    by_day: list[CostRow]


class RoleModel(In):
    provider_id: str | None = None
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1500, ge=16, le=32_000)


class WritingSettings(In):
    roles: dict[Role, RoleModel] = Field(default_factory=dict)
    #: The critic's overall score (0-10) a draft needs to skip further editing.
    pass_threshold: float = Field(default=7.5, ge=0, le=10)
    #: Editor rewrites after the first draft.
    max_iterations: int = Field(default=2, ge=0, le=6)
    #: Token budget for the assembled context.
    context_tokens: int = Field(default=6000, ge=500, le=200_000)
