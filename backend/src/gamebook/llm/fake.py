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
        case "consistency":
            return json.dumps({"issues": _consistency(prompt)})
        case "suggester":
            return json.dumps(_suggest(prompt))
        case "lore_extractor":
            return json.dumps(_extract(prompt))
        case "player":
            return json.dumps(_play(prompt))
    return "OK"


def _consistency(prompt: str) -> list[dict[str, str]]:
    """Flags prose that names something only some readers have."""
    prose = _between(prompt, "prose")
    names = []
    for part in _between(prompt, "may").split(";"):
        _, _, values = part.partition(":")
        names += [v.strip() for v in values.split(",") if v.strip()]
    issues = []
    for name in names:
        m = re.search(rf"[^.!?]*\b{re.escape(name)}\b[^.!?]*[.!?]?", prose, re.I)
        if m:
            issues.append(
                {
                    "severity": "warning",
                    "kind": "path_validity",
                    "quote": m.group(0).strip(),
                    "problem": f"Assumes the reader has {name}, but only some readers do.",
                    "suggestion": f"Mention {name} only in a variant for readers who have it.",
                }
            )
    return issues


def _suggest(prompt: str) -> dict[str, Any]:
    """One new section per beat without sections, linked from the last open section."""
    rows = [r.split("|") for r in _between(prompt, "nodes").splitlines() if r.strip()]
    nodes = [{"key": r[0], "title": r[1], "flags": r[2] if len(r) > 2 else ""} for r in rows]
    open_nodes = [n for n in nodes if "ending" not in n["flags"]]
    endings = [n for n in nodes if "ending" in n["flags"]]
    out_nodes: list[dict[str, str]] = []
    choices: list[dict[str, str]] = []
    beats = [b.split("|", 1) for b in _between(prompt, "unlinked_beats").splitlines() if b.strip()]
    for i, beat in enumerate(beats):
        ref = f"new{i + 1}"
        title = beat[0].strip()
        out_nodes.append(
            {
                "ref": ref,
                "title": title,
                "beat_notes": (beat[1].strip() if len(beat) > 1 else "") or f"The {title} happens.",
                "beat": title,
            }
        )
        if open_nodes:
            choices.append({"from": open_nodes[-1]["key"], "to": ref, "label": f"Go on: {title}"})
        if endings:
            choices.append({"from": ref, "to": endings[0]["key"], "label": "Press on"})
    return {
        "rationale": "Adds a section for each story beat that has none yet.",
        "nodes": out_nodes,
        "choices": choices,
    }


def _extract(prompt: str) -> dict[str, Any]:
    """'named X' → a character, 'called X' → a place; existing names become updates."""
    existing = {}
    for row in _between(prompt, "existing").splitlines():
        parts = row.split("|")
        if len(parts) == 3:
            existing[parts[2].strip().lower()] = (parts[0].strip(), parts[1].strip())
    text = "\n".join(re.findall(r"<section[^>]*>(.*?)</section>", prompt, re.S))
    characters: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for m in re.finditer(r"named ([A-Z][a-z]+)", text):
        name = m.group(1)
        hit = existing.get(name.lower())
        sentence = re.search(rf"[^.!?]*{name}[^.!?]*[.!?]", text)
        characters.append(
            {
                "name": name,
                "existing_key": hit[1] if hit and hit[0] == "character" else None,
                "role": "",
                "notes": sentence.group(0).strip() if sentence else "",
                "evidence": sentence.group(0).strip() if sentence else name,
            }
        )
    for m in re.finditer(r"called the ([A-Z][a-z]+(?: [A-Z][a-z]+)*)", text):
        name = m.group(1)
        hit = existing.get(name.lower())
        sentence = re.search(rf"[^.!?]*{name}[^.!?]*[.!?]", text)
        entries.append(
            {
                "name": name,
                "existing_key": hit[1] if hit and hit[0] == "lore" else None,
                "type": "location",
                "body": sentence.group(0).strip() if sentence else "",
                "evidence": sentence.group(0).strip() if sentence else name,
            }
        )
    return {"characters": characters, "entries": entries}


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


def _play(prompt: str) -> dict[str, Any]:
    """Attack when fighting, else take the first option; confused by sections with no text."""
    options = [
        re.sub(r"^\d+\.\s*", "", o).strip()
        for o in _between(prompt, "options").splitlines()
        if o.strip()
    ]
    page = _between(prompt, "page")
    pick = next((i for i, o in enumerate(options) if o.lower().startswith("attack")), 0)
    confused = "(This section has no text yet.)" in page
    return {
        "choice": pick + 1,
        "reasoning": f"I'll {options[pick].lower() if options else 'carry on'}.",
        "memory": "I am exploring and trying to survive.",
        "confused": confused,
        "confusion": "There's no text here, so I can't tell what is happening." if confused else "",
    }
