"""Rule-system definition (stored as JSON) and tier inheritance.

Tiers are ordered (basic < medium < advanced …). Each tier names a parent and
declares only what it adds or overrides; :func:`effective_tier` merges the chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gamebook.core.effects import Effect
from gamebook.core.keys import KEY_PATTERN

Applies = Literal["player", "enemy"]


def _player_only() -> list[Applies]:
    return ["player"]


class _Def(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StatDef(_Def):
    key: str = Field(pattern=KEY_PATTERN)
    label: str
    description: str = ""
    kind: Literal["stat", "resource"] = "stat"
    applies_to: list[Applies] = Field(default_factory=_player_only)
    #: gbx rolled at character creation (player only).
    initial: str = "0"
    min: int | None = 0
    max: int | None = None
    #: The starting value is also the maximum (classic SKILL/STAMINA).
    max_is_initial: bool = False
    #: Reaching this value means defeat (e.g. STAMINA 0).
    defeat_at: int | None = None


class TestDef(_Def):
    key: str = Field(pattern=KEY_PATTERN)
    label: str
    description: str = ""
    roll: str = "2d6"
    #: gbx bool; ``roll`` is the total rolled.
    success: str
    after: list[Effect] = Field(default_factory=list)


class SkillDef(_Def):
    key: str = Field(pattern=KEY_PATTERN)
    label: str
    description: str = ""


class ClassDef(_Def):
    key: str = Field(pattern=KEY_PATTERN)
    label: str
    description: str = ""
    skills: list[str] = Field(default_factory=list)


class CombatDef(_Def):
    """Combat is a fixed procedure with expression hooks (SPEC §2.4).

    Each round both sides roll attack strength; the higher one deals ``damage``
    to the other's ``damage_stat``, passed through ``damage_hooks`` in order.
    Fields left None inherit from the parent tier; hooks accumulate.
    """

    player_attack: str | None = None
    enemy_attack: str | None = None
    damage: str | None = None
    damage_stat: str | None = None
    damage_hooks: list[str] = Field(default_factory=list)
    multi_enemy: Literal["sequential", "simultaneous"] | None = None
    flee_allowed: bool | None = None
    flee_cost: list[Effect] | None = None


class TierDef(_Def):
    key: str = Field(pattern=KEY_PATTERN)
    label: str
    parent: str | None = None
    description: str = ""
    stats: list[StatDef] = Field(default_factory=list)
    tests: list[TestDef] = Field(default_factory=list)
    skills: list[SkillDef] = Field(default_factory=list)
    classes: list[ClassDef] = Field(default_factory=list)
    slots: list[str] = Field(default_factory=list)
    combat: CombatDef = Field(default_factory=CombatDef)
    #: Author-written rules chapter text for this tier (markdown).
    rules_text: str = ""


class RuleSystemDef(_Def):
    tiers: list[TierDef] = Field(min_length=1)

    def tier_keys(self) -> tuple[str, ...]:
        return tuple(t.key for t in self.tiers)

    def tier(self, key: str) -> TierDef | None:
        return next((t for t in self.tiers if t.key == key), None)


class TierError(ValueError):
    pass


@dataclass(frozen=True)
class EffectiveTier:
    key: str
    label: str
    index: int
    stats: dict[str, StatDef]
    tests: dict[str, TestDef]
    skills: dict[str, SkillDef]
    classes: dict[str, ClassDef]
    slots: tuple[str, ...]
    combat: CombatDef
    #: Which tier introduced each stat (for "inherited" display).
    stat_origin: dict[str, str]

    def player_stats(self) -> frozenset[str]:
        return frozenset(k for k, s in self.stats.items() if "player" in s.applies_to)

    def enemy_stats(self) -> frozenset[str]:
        return frozenset(k for k, s in self.stats.items() if "enemy" in s.applies_to)


def tier_chain(system: RuleSystemDef, key: str) -> list[TierDef]:
    """Root-first ancestry of a tier. Raises TierError on missing/cyclic parents."""
    by_key = {t.key: t for t in system.tiers}
    if key not in by_key:
        raise TierError(f"Unknown tier {key!r}")
    chain: list[TierDef] = []
    seen: set[str] = set()
    cur: str | None = key
    while cur is not None:
        if cur in seen:
            raise TierError(f"Tier {key!r} has a cyclic parent chain")
        if cur not in by_key:
            raise TierError(f"Tier {chain[-1].key!r} has unknown parent {cur!r}")
        seen.add(cur)
        chain.append(by_key[cur])
        cur = by_key[cur].parent
    return list(reversed(chain))


def effective_tier(system: RuleSystemDef, key: str) -> EffectiveTier:
    chain = tier_chain(system, key)
    stats: dict[str, StatDef] = {}
    origin: dict[str, str] = {}
    tests: dict[str, TestDef] = {}
    skills: dict[str, SkillDef] = {}
    classes: dict[str, ClassDef] = {}
    slots: list[str] = []
    combat_fields: dict[str, object] = {}
    hooks: list[str] = []
    for t in chain:
        for s in t.stats:
            stats[s.key] = s
            origin.setdefault(s.key, t.key)
        tests.update({x.key: x for x in t.tests})
        skills.update({x.key: x for x in t.skills})
        classes.update({x.key: x for x in t.classes})
        slots.extend(s for s in t.slots if s not in slots)
        for name in CombatDef.model_fields:
            value = getattr(t.combat, name)
            if name == "damage_hooks":
                hooks.extend(value)
            elif value is not None:
                combat_fields[name] = value
    top = chain[-1]
    return EffectiveTier(
        key=top.key,
        label=top.label,
        index=system.tier_keys().index(top.key),
        stats=stats,
        tests=tests,
        skills=skills,
        classes=classes,
        slots=tuple(slots),
        combat=CombatDef.model_validate({**combat_fields, "damage_hooks": hooks}),
        stat_origin=origin,
    )
