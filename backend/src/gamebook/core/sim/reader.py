"""What a reader sees at the current moment, as plain text (the LLM player's eyes).

Only reader-visible information: the section's text (approved prose, else the
author's beat notes as a stand-in), what just happened (narrated events, dice
included — readers roll them), the adventure sheet, any fight in progress, and
the numbered options. No section titles, node keys, conditions or hidden state.
"""

from __future__ import annotations

from dataclasses import dataclass

from gamebook.core.engine.events import Action, Event
from gamebook.core.engine.game import Game
from gamebook.core.engine.narrate import Names, narrate

NO_TEXT = "(This section has no text yet.)"


@dataclass(frozen=True)
class Page:
    text: str
    options: list[str]


def render_page(
    game: Game,
    options: list[Action],
    events: list[Event],
    *,
    names: Names,
    prose: dict[str, str],
    beat_notes: dict[str, str],
) -> Page:
    s = game.state
    parts: list[str] = []
    variant = s.variant_id or ""
    body = prose.get(variant) or beat_notes.get(s.node_id or "", "").strip() or NO_TEXT
    parts.append(body)

    happened = [
        line
        for e in events
        # Content errors name conditions and expressions: author-only, never shown.
        if e.type not in ("enter", "action", "outcome", "debug", "error")
        and (line := narrate(e, names))
    ]
    if happened:
        parts.append("WHAT JUST HAPPENED\n" + "\n".join(f"- {line}" for line in happened))

    sheet = []
    effective = game.effective_stats()
    for key, sd in game.tier.stats.items():
        if "player" not in sd.applies_to:
            continue
        value = effective.get(key, s.stats.get(key, 0))
        cap = s.max_stats.get(key)
        sheet.append(f"{sd.label} {value}" + (f"/{cap}" if cap is not None else ""))
    items = [
        names.items.get(k, k) + (f" x{n}" if n > 1 else "")
        for k, n in sorted(s.items.items())
        if n > 0
    ]
    lines = ["YOUR ADVENTURE SHEET", ", ".join(sheet)]
    if s.character_class:
        lines.append(f"Class: {s.character_class}")
    if s.skills:
        lines.append("Skills: " + ", ".join(names.skills.get(k, k) for k in sorted(s.skills)))
    lines.append("Items: " + (", ".join(items) if items else "none"))
    if s.equipped:
        lines.append("Equipped: " + ", ".join(names.items.get(k, k) for k in s.equipped.values()))
    if s.flags:
        lines.append("Codewords: " + ", ".join(sorted(s.flags)))
    parts.append("\n".join(lines))

    if s.combat is not None:
        foes = "; ".join(
            f"{names.enemy(e.key)} (level {e.level}): "
            + ", ".join(f"{k} {v}" for k, v in sorted(e.stats.items()))
            for e in s.combat.enemies
        )
        parts.append(f"YOU ARE FIGHTING (round {s.combat.round})\n{foes}")

    # The options are listed separately (the prompt numbers them).
    labels = [a.label or "(unlabelled choice)" for a in options]
    return Page(text="\n\n".join(parts), options=labels)
