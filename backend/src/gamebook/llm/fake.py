"""The offline test model: deterministic, no network.

It lets the whole prose pipeline run in tests, e2e and demos. Prompts are read
through the markers the default templates use (``<beat_notes>``, ``<draft>``,
``<choices>``). Tests can queue exact responses per role in ``SCRIPT``.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from gamebook.llm.client import Completion, Message, estimate_tokens

#: role → queued responses (consumed first; tests fill this).
SCRIPT: defaultdict[str, list[str]] = defaultdict(list)

REVISED = "The air itself seems to listen as you decide."


def _between(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, re.S)
    return m.group(1).strip() if m else ""


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def _respond(role: str, prompt: str) -> str:
    match role:
        case "writer":
            notes = _between(prompt, "beat_notes") or "Nothing much happens here."
            choices = [
                c.strip("- ").strip() for c in _between(prompt, "choices").splitlines() if c.strip()
            ]
            body = " ".join(_sentences(notes)) or notes
            lines = [f"You take in the scene. {body}"]
            if choices:
                lines.append("Before you, the way divides: " + "; ".join(choices) + ".")
            return "\n\n".join(lines)
        case "editor":
            draft = _between(prompt, "draft")
            return f"{draft}\n\n{REVISED}" if REVISED not in draft else draft
        case "critic":
            draft = _between(prompt, "draft")
            good = REVISED in draft
            score = 8 if good else 6
            report: dict[str, Any] = {
                "scores": {
                    "beat_adherence": score,
                    "continuity": score,
                    "path_validity": score,
                    "style": score,
                    "choice_setup": score,
                    "prose_quality": score,
                },
                "overall": score,
                "issues": []
                if good
                else [
                    {
                        "quote": (_sentences(draft) or [""])[0][:80],
                        "problem": "The ending doesn't build tension before the choice.",
                        "suggestion": "Close on a beat of atmosphere that leads into the choices.",
                    }
                ],
                "summary": "Ready for review." if good else "Serviceable but flat at the end.",
            }
            return json.dumps(report)
        case "summarizer":
            text = _between(prompt, "text")
            return " ".join(_sentences(text)[:2]) or text[:200]
    return "OK"


class FakeClient:
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
        prompt = "\n".join(m["content"] for m in messages)
        text = SCRIPT[role].pop(0) if SCRIPT[role] else _respond(role, prompt)
        return Completion(
            text=text,
            prompt_tokens=estimate_tokens(prompt),
            completion_tokens=estimate_tokens(text),
            latency_ms=1,
        )

    def list_models(self) -> list[str]:
        return ["offline-writer"]
