"""Mutable game state. Everything is plain data so it can be snapshotted to JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Combatant:
    key: str
    name: str
    stats: dict[str, int]
    level: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "level": self.level,
            "stats": dict(sorted(self.stats.items())),
        }


@dataclass
class CombatState:
    choice_id: str
    enemies: list[Combatant]
    simultaneous: bool
    flee_allowed: bool
    round: int = 0

    def alive(self, damage_stat: str, defeat_at: int) -> list[Combatant]:
        return [e for e in self.enemies if e.stats.get(damage_stat, 0) > defeat_at]

    def to_dict(self) -> dict[str, Any]:
        return {
            "choice_id": self.choice_id,
            "enemies": [e.to_dict() for e in self.enemies],
            "simultaneous": self.simultaneous,
            "flee_allowed": self.flee_allowed,
            "round": self.round,
        }


@dataclass
class GameState:
    tier: str
    stats: dict[str, int] = field(default_factory=dict)
    max_stats: dict[str, int] = field(default_factory=dict)
    items: dict[str, int] = field(default_factory=dict)  # item key -> count
    equipped: dict[str, str] = field(default_factory=dict)  # slot -> item key
    flags: set[str] = field(default_factory=set)
    skills: set[str] = field(default_factory=set)
    character_class: str | None = None
    #: Classes the reader must pick from before anything else (a choose-class effect).
    class_pending: list[str] | None = None
    node_id: str | None = None
    variant_id: str | None = None
    visits: dict[str, int] = field(default_factory=dict)  # node key -> count
    fired: set[str] = field(default_factory=set)  # once-only effect / pickup keys
    shop_stock: dict[str, int] = field(default_factory=dict)  # "node:index" -> remaining
    combat: CombatState | None = None
    #: None while playing; otherwise victory | death | dead_end | defeated | stuck
    ended: str | None = None
    ending_node_id: str | None = None
    steps: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "stats": dict(sorted(self.stats.items())),
            "max_stats": dict(sorted(self.max_stats.items())),
            "items": {k: v for k, v in sorted(self.items.items()) if v > 0},
            "equipped": dict(sorted(self.equipped.items())),
            "flags": sorted(self.flags),
            "skills": sorted(self.skills),
            "class": self.character_class,
            "class_pending": self.class_pending,
            "node_id": self.node_id,
            "variant_id": self.variant_id,
            "visits": dict(sorted(self.visits.items())),
            "combat": self.combat.to_dict() if self.combat else None,
            "ended": self.ended,
            "ending_node_id": self.ending_node_id,
            "steps": self.steps,
        }
