"""Tolerant JSON extraction from model output (code fences, chatter, trailing commas)."""

from __future__ import annotations

import json
import re
from typing import Any


class BadJson(ValueError):  # noqa: N818 - reads naturally at call sites
    pass


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def _first_object(text: str) -> str | None:
    """The first balanced {...} block (string-aware)."""
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def parse_object(text: str) -> dict[str, Any]:
    candidates = [text.strip()]
    candidates += [m.group(1).strip() for m in _FENCE.finditer(text)]
    block = _first_object(text)
    if block:
        candidates.append(block)
    for c in candidates:
        for attempt in (c, _TRAILING_COMMA.sub(r"\1", c)):
            try:
                value = json.loads(attempt)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    raise BadJson(f"No JSON object found in: {text[:200]!r}")
