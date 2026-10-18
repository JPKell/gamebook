"""Opt-in smoke test against a real OpenAI-compatible endpoint.

Runs only when GAMEBOOK_LIVE_LLM_URL and GAMEBOOK_LIVE_LLM_MODEL are set, e.g.:

    GAMEBOOK_LIVE_LLM_URL=http://localhost:11434/v1 GAMEBOOK_LIVE_LLM_MODEL=llama3.1 \\
        uv run pytest tests/test_llm_live.py

Set GAMEBOOK_LIVE_LLM_KEY_ENV to the name of an env var holding the API key if needed.
"""

from __future__ import annotations

import os

import pytest

from gamebook.llm.client import OpenAIClient, ProviderConfig
from gamebook.llm.jsonparse import parse_object
from gamebook.llm.templates import CRITIC_SCHEMA

URL = os.environ.get("GAMEBOOK_LIVE_LLM_URL")
MODEL = os.environ.get("GAMEBOOK_LIVE_LLM_MODEL")

pytestmark = pytest.mark.skipif(not (URL and MODEL), reason="live LLM not configured")


def test_live_completion_and_json() -> None:
    assert URL
    assert MODEL
    client = OpenAIClient(
        ProviderConfig(
            id="live",
            kind="openai",
            base_url=URL,
            api_key_env=os.environ.get("GAMEBOOK_LIVE_LLM_KEY_ENV"),
        )
    )
    prose = client.complete(
        MODEL,
        [{"role": "user", "content": "Write one sentence about a raven on a gate."}],
        role="writer",
        max_tokens=80,
    )
    assert prose.text.strip()
    report = client.complete(
        MODEL,
        [
            {
                "role": "user",
                "content": 'Rate "The raven waits." Reply with JSON only: '
                '{"scores": {"beat_adherence": n, "continuity": n, "path_validity": n, '
                '"style": n, "choice_setup": n, "prose_quality": n}, "overall": n, "issues": []}',
            }
        ],
        role="critic",
        max_tokens=300,
        json_schema=CRITIC_SCHEMA,
    )
    assert "overall" in parse_object(report.text)
