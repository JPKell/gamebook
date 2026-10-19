"""The TypeScript engine's parity corpus must match the Python engine (like golden traces)."""

from __future__ import annotations

import json

from . import parity_corpus


def test_parity_corpus_is_current() -> None:
    committed = json.loads(parity_corpus.OUT.read_text())
    assert json.loads(json.dumps(parity_corpus.build())) == committed, (
        "engine behaviour changed: regenerate with `uv run python -m tests.core.parity_corpus` "
        "and check the TS engine still passes frontend/src/engine/parity.test.ts"
    )
