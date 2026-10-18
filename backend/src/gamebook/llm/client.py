"""OpenAI-compatible chat completions (local servers, OpenAI, OpenRouter).

Synchronous on purpose: pipelines run in the job thread. Each provider has a
process-wide semaphore (``max_concurrency``). Transient failures (connection
errors, timeouts, 429 and 5xx) are retried with exponential backoff, honouring
``Retry-After``.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

Message = dict[str, str]


class LlmError(Exception):
    """A call failed for good (after retries), or the provider is misconfigured.

    ``cost_usd`` is what was already spent on the way (e.g. a pipeline that failed
    after several successful calls), so budgets can count it.
    """

    def __init__(self, message: str, *, cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.cost_usd = cost_usd


@dataclass(frozen=True)
class Completion:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


@dataclass(frozen=True)
class ProviderConfig:
    id: str
    kind: str  # openai | fake
    base_url: str
    api_key_env: str | None = None
    max_concurrency: int = 2
    timeout_s: float = 120.0
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env) if self.api_key_env else None


class ChatClient(Protocol):
    def complete(
        self,
        model: str,
        messages: list[Message],
        *,
        role: str,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        json_schema: dict[str, Any] | None = None,
    ) -> Completion: ...


_locks: dict[str, threading.BoundedSemaphore] = {}
_locks_guard = threading.Lock()


def _slot(cfg: ProviderConfig) -> threading.BoundedSemaphore:
    with _locks_guard:
        key = f"{cfg.id}:{cfg.max_concurrency}"
        if key not in _locks:
            _locks[key] = threading.BoundedSemaphore(max(1, cfg.max_concurrency))
        return _locks[key]


def estimate_tokens(text: str) -> int:
    """Rough token count (≈4 characters per token) when the server doesn't report usage."""
    return max(1, len(text) // 4)


class OpenAIClient:
    RETRY_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

    def __init__(
        self,
        cfg: ProviderConfig,
        *,
        retries: int = 3,
        backoff_s: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not cfg.base_url:
            raise LlmError("The provider has no base URL")
        if cfg.api_key_env and not cfg.api_key:
            raise LlmError(f"Environment variable {cfg.api_key_env} is not set")
        self.cfg = cfg
        self.retries = retries
        self.backoff_s = backoff_s
        headers = {"Content-Type": "application/json", **cfg.headers}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        self.http = httpx.Client(
            base_url=cfg.base_url.rstrip("/") + "/",
            headers=headers,
            timeout=cfg.timeout_s,
            transport=transport,
        )

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                res = self.http.post("chat/completions", json=payload)
            except httpx.TimeoutException as exc:
                # A slow model won't get faster: don't re-bill a long generation.
                raise LlmError(f"Timed out after {self.cfg.timeout_s:.0f} s") from exc
            except httpx.TransportError as exc:
                last = exc
                delay = self.backoff_s * 2**attempt
            else:
                if res.status_code < 400:
                    data: dict[str, Any] = res.json()
                    return data
                body = res.text[:500]
                if res.status_code not in self.RETRY_STATUS:
                    raise LlmError(f"HTTP {res.status_code}: {body}")
                last = LlmError(f"HTTP {res.status_code}: {body}")
                retry_after = res.headers.get("retry-after")
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.replace(".", "", 1).isdigit()
                    else self.backoff_s * 2**attempt
                )
            if attempt < self.retries:
                time.sleep(min(delay, 60.0))
        raise LlmError(f"Gave up after {self.retries + 1} attempts: {last}")

    def complete(
        self,
        model: str,
        messages: list[Message],
        *,
        role: str,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        json_schema: dict[str, Any] | None = None,
    ) -> Completion:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": role, "schema": json_schema},
            }
        started = time.monotonic()
        with _slot(self.cfg):
            try:
                data = self._post(payload)
            except LlmError as exc:
                # Some servers reject structured output (wording varies); ask again
                # without it — the caller parses tolerantly and re-asks if needed.
                if json_schema is None or not str(exc).startswith(("HTTP 400", "HTTP 422")):
                    raise
                payload.pop("response_format")
                data = self._post(payload)
        latency = int((time.monotonic() - started) * 1000)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmError(f"Unexpected response: {str(data)[:300]}") from exc
        usage = data.get("usage") or {}
        prompt = "\n".join(m["content"] for m in messages)
        return Completion(
            text=text,
            prompt_tokens=int(usage.get("prompt_tokens") or estimate_tokens(prompt)),
            completion_tokens=int(usage.get("completion_tokens") or estimate_tokens(text)),
            latency_ms=latency,
        )

    def close(self) -> None:
        self.http.close()

    def list_models(self) -> list[str]:
        res = self.http.get("models")
        if res.status_code >= 400:
            raise LlmError(f"HTTP {res.status_code}: {res.text[:300]}")
        data = res.json()
        return sorted(str(m["id"]) for m in data.get("data", []) if "id" in m)


def client_for(cfg: ProviderConfig) -> ChatClient:
    if cfg.kind == "fake":
        from gamebook.llm.fake import FakeClient

        return FakeClient()
    return OpenAIClient(cfg)
