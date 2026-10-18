"""OpenAI-compatible client: retries, fallbacks, usage; tolerant JSON parsing."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from gamebook.llm.client import LlmError, OpenAIClient, ProviderConfig
from gamebook.llm.jsonparse import BadJson, parse_object

CFG = ProviderConfig(id="p", kind="openai", base_url="http://llm.test/v1")


def _ok(text: str, usage: dict[str, int] | None = None) -> httpx.Response:
    body: dict[str, object] = {"choices": [{"message": {"content": text}}]}
    if usage:
        body["usage"] = usage
    return httpx.Response(200, json=body)


def client(handler: Callable[[httpx.Request], httpx.Response], **kw: Any) -> OpenAIClient:
    return OpenAIClient(
        CFG,
        transport=httpx.MockTransport(handler),
        backoff_s=0,
        **kw,
    )


def test_retries_transient_errors_then_reports_usage() -> None:
    seen: list[dict[str, object]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        if len(seen) < 3:
            return httpx.Response(429 if len(seen) == 1 else 503, headers={"retry-after": "0"})
        return _ok("Hello", {"prompt_tokens": 12, "completion_tokens": 3})

    c = client(handler).complete("m", [{"role": "user", "content": "hi"}], role="writer")
    assert c.text == "Hello"
    assert (c.prompt_tokens, c.completion_tokens) == (12, 3)
    assert len(seen) == 3
    assert str(seen[0]["model"]) == "m"


def test_client_errors_are_not_retried() -> None:
    calls = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, text="bad key")

    with pytest.raises(LlmError, match="HTTP 401"):
        client(handler).complete("m", [{"role": "user", "content": "x"}], role="writer")
    assert calls == 1


def test_gives_up_after_retries() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(LlmError, match="Gave up after 3 attempts"):
        client(handler, retries=2).complete("m", [{"role": "user", "content": "x"}], role="w")


def test_falls_back_when_response_format_is_rejected() -> None:
    bodies: list[dict[str, object]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        bodies.append(body)
        if "response_format" in body:
            return httpx.Response(400, text="response_format is not supported")
        return _ok('{"overall": 7}')

    c = client(handler).complete(
        "m", [{"role": "user", "content": "x"}], role="critic", json_schema={"type": "object"}
    )
    assert c.text == '{"overall": 7}'
    assert ["response_format" in b for b in bodies] == [True, False]
    assert c.prompt_tokens > 0  # estimated when the server reports no usage


def test_missing_key_env_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GB_TEST_KEY", raising=False)
    with pytest.raises(LlmError, match="GB_TEST_KEY is not set"):
        OpenAIClient(
            ProviderConfig(id="p", kind="openai", base_url="http://x", api_key_env="GB_TEST_KEY")
        )


def test_lists_models() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "b"}, {"id": "a"}]})

    assert client(handler).list_models() == ["a", "b"]


@pytest.mark.parametrize(
    "text",
    [
        '{"overall": 8}',
        'Sure! Here you go:\n```json\n{"overall": 8}\n```',
        'Report: {"overall": 8, "issues": [],} thanks',
        'noise {"overall": 8, "note": "has } brace"} more',
    ],
)
def test_parse_object_is_tolerant(text: str) -> None:
    assert parse_object(text)["overall"] == 8


def test_parse_object_rejects_non_json() -> None:
    with pytest.raises(BadJson):
        parse_object("I give it an 8.")
