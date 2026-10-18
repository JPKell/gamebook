"""Plain-English lines for engine events (the player's mechanics blocks and logs).

Narration is presentation only: it never changes what happened, and an event
with nothing worth saying returns ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gamebook.core.engine.events import Event
from gamebook.core.engine.game import Game

ENDING_LABELS = {
    "victory": "Victory",
    "death": "Death",
    "dead_end": "Dead end",
    "defeated": "Defeated",
    "stuck": "Stuck",
}


@dataclass(frozen=True)
class Names:
    nodes: dict[str, str] = field(default_factory=dict)
    choices: dict[str, str] = field(default_factory=dict)
    items: dict[str, str] = field(default_factory=dict)
    stats: dict[str, str] = field(default_factory=dict)
    tests: dict[str, str] = field(default_factory=dict)
    skills: dict[str, str] = field(default_factory=dict)
    enemies: dict[str, str] = field(default_factory=dict)

    @classmethod
    def for_game(cls, game: Game) -> Names:
        book, tier = game.book, game.tier
        return cls(
            nodes={n.id: n.title for n in book.nodes},
            choices={c.id: c.label for n in book.nodes for c in n.choices},
            items={i.key: i.name for i in book.items},
            stats={k: s.label for k, s in tier.stats.items()},
            tests={k: t.label for k, t in tier.tests.items()},
            skills={k: s.label for k, s in tier.skills.items()},
            enemies={e.key: e.name for e in book.enemies},
        )

    def enemy(self, key: str) -> str:
        base, _, n = key.partition("#")
        name = self.enemies.get(base, base)
        return f"{name} {n}" if n else name


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def narrate(event: Event, names: Names) -> str | None:
    d: dict[str, Any] = event.data
    stat = names.stats.get(str(d.get("stat")), str(d.get("stat")))
    item = names.items.get(str(d.get("item")), str(d.get("item")))
    match event.type:
        case "character_created":
            parts = [f"{names.stats.get(k, k)} {v}" for k, v in d["stats"].items()]
            who = f" ({d['class']})" if d.get("class") else ""
            return f"Character created{who}: " + ", ".join(parts)
        case "roll":
            faces = d.get("faces") or []
            if not faces and not d.get("forced"):
                return f"{d['purpose'].capitalize()}: {d['total']}"
            how = " + ".join(map(str, faces)) + " = " if len(faces) > 1 else ""
            forced = " (forced)" if d.get("forced") else ""
            return f"Rolled {d['expr']} for {d['purpose']}: {how}{d['total']}{forced}"
        case "enter":
            return None
        case "action":
            return None
        case "outcome":
            return None
        case "effect":
            match d.get("op"):
                case "modify":
                    if not d.get("change"):
                        return None
                    return f"{stat} {_signed(d['change'])} (now {d['value']})"
                case "set":
                    return f"{stat} set to {d['value']}"
                case "give":
                    return f"Gained {item} x{d['qty']}" if d.get("qty") else None
                case "take":
                    return f"Lost {item} x{d['qty']}" if d.get("qty") else None
                case "equip":
                    return f"Equipped {item}"
                case "set_flag":
                    return f"Codeword noted: {d['flag']}"
                case "clear_flag":
                    return f"Codeword removed: {d['flag']}"
                case "learn":
                    return f"Learned {names.skills.get(d['skill'], d['skill'])}"
            return None
        case "test":
            label = names.tests.get(d["test"], d["test"])
            return f"{label}: {'success' if d['success'] else 'failure'} (rolled {d['roll']})"
        case "table":
            result = d.get("result") or "no result"
            return f"Random table {d['table']}: rolled {d['roll']} → {result}"
        case "combat_start":
            foes = ", ".join(
                f"{names.enemy(e['key'])} (level {e['level']})" for e in d.get("enemies", [])
            )
            return f"Combat begins: {foes}"
        case "combat_round":
            foe = names.enemy(d["enemy"])
            head = (
                f"Round {d['round']} vs {foe}: you {d['player_attack']}, {foe} {d['enemy_attack']}"
            )
            if d.get("hit") == "enemy":
                return f"{head} — you hit for {d['damage']} ({d['remaining']} left)"
            if d.get("hit") == "player":
                return f"{head} — you take {d['damage']} ({d['remaining']} left)"
            return f"{head} — no damage"
        case "enemy_defeated":
            return f"{names.enemy(d['enemy'])} is defeated"
        case "combat_end":
            return {
                "win": "You won the fight",
                "lose": "You lost the fight",
                "flee": "You fled",
            }.get(d["outcome"], f"Combat over: {d['outcome']}")
        case "combat_stalemate":
            return f"Stalemate after {d['rounds']} rounds"
        case "combat_skipped":
            return "No enemies appeared"
        case "combat_unconfigured":
            return "The rules have no combat procedure; the fight is skipped"
        case "item_taken":
            return f"Took {item} x{d['qty']}" if d.get("qty") else f"Couldn't carry more {item}"
        case "item_bought":
            return f"Bought {item} for {d['price']}"
        case "item_sold":
            return f"Sold {item} for {d['price']}"
        case "item_used":
            return f"Used {item}"
        case "equipped":
            return f"Equipped {item}"
        case "unequipped":
            return f"Unequipped {item}"
        case "game_over":
            label = ENDING_LABELS.get(d["ending"], d["ending"])
            return f"{label}" + (f" — {d['reason']}" if d.get("reason") else "")
        case "error":
            return f"Content error in {d['where']}: {d['message']}"
        case "debug":
            match d.get("op"):
                case "jump":
                    return f"[debug] Jumped to {names.nodes.get(d['node'], d['node'])}"
                case "set":
                    return "[debug] State edited"
                case "force":
                    return f"[debug] Next roll forced to {d['total']}"
    return None
