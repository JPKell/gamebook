"""Rule-system definition (stored as JSON) and tier inheritance.

Tiers are ordered (basic < medium < advanced …). Each tier names a parent and
declares only what it adds or overrides; :func:`effective_tier` merges the chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

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


class StatBonus(_Def):
    """Add ``amount`` (gbx, dice allowed) to a player stat — and to its maximum
    when the maximum is the starting value."""

    stat: str = Field(pattern=KEY_PATTERN)
    amount: str = "1"


class StartingItem(_Def):
    item: str = Field(pattern=KEY_PATTERN)
    qty: int = Field(default=1, ge=1, le=999)
    #: Equip it straight away (when it has a slot this tier uses).
    equip: bool = False


class ClassDef(_Def):
    key: str = Field(pattern=KEY_PATTERN)
    label: str
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    #: Applied once at character creation, after the stats are rolled.
    modifiers: list[StatBonus] = Field(default_factory=list)
    #: Given at character creation, after the tier's own starting items.
    starting_items: list[StartingItem] = Field(default_factory=list)


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


class ProgressionDef(_Def):
    """Experience and levels (SPEC §2.4a). Fields left None inherit from the parent tier.

    Winning a fight awards ``xp_award`` per enemy defeated (variables ``enemy_level``
    and ``level``, the reader's level) to ``xp_stat``. While XP reaches
    ``xp_to_next`` (variable ``level``), that much XP is spent, ``level_stat``
    goes up by one and every ``level_up`` bonus is applied.
    """

    xp_stat: str | None = None
    level_stat: str | None = None
    xp_award: str | None = None
    xp_to_next: str | None = None
    max_level: int | None = Field(default=None, ge=1)
    level_up: list[StatBonus] | None = None

    def enabled(self) -> bool:
        return bool(self.xp_stat and self.level_stat and self.xp_to_next)


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
    progression: ProgressionDef = Field(default_factory=ProgressionDef)
    #: When the reader picks a class: at character creation, or later through a
    #: "choose class" effect in the story. None inherits (default: start).
    class_choice: Literal["start", "story"] | None = None
    #: Given to every reader at character creation (accumulates down the tiers).
    starting_items: list[StartingItem] = Field(default_factory=list)
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
    progression: ProgressionDef = field(default_factory=ProgressionDef)
    starting_items: tuple[StartingItem, ...] = ()
    class_choice: str = "start"

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
    progression: dict[str, object] = {}
    starting: list[StartingItem] = []
    class_choice = "start"
    for t in chain:
        starting.extend(t.starting_items)
        class_choice = t.class_choice or class_choice
        for name in ProgressionDef.model_fields:
            if (value := getattr(t.progression, name)) is not None:
                progression[name] = value
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
        progression=ProgressionDef.model_validate(progression),
        starting_items=tuple(starting),
        class_choice=class_choice,
    )


def tier_view(system: RuleSystemDef, key: str) -> dict[str, object]:
    """The merged tier plus provenance for each part, for editors.

    For each stat/test/skill/class: ``introduced`` (first tier defining the key)
    and ``origin`` (tier whose definition is in effect, i.e. the last override).
    Combat scalars carry the tier that set them; hooks list their tier.
    """
    chain = tier_chain(system, key)
    eff = effective_tier(system, key)

    def provenance(attr: str) -> dict[str, tuple[str, str]]:
        out: dict[str, tuple[str, str]] = {}
        for t in chain:
            for d in getattr(t, attr):
                first = out[d.key][0] if d.key in out else t.key
                out[d.key] = (first, t.key)
        return out

    def rows(attr: str, merged: dict[str, Any]) -> list[dict[str, object]]:
        prov = provenance(attr)
        return [
            {**d.model_dump(mode="json"), "introduced": prov[k][0], "origin": prov[k][1]}
            for k, d in merged.items()
        ]

    slot_origin: dict[str, str] = {}
    combat_origin: dict[str, str] = {}
    progression_origin: dict[str, str] = {}
    hooks: list[dict[str, str]] = []
    starting: list[dict[str, object]] = []
    for t in chain:
        starting += [{**si.model_dump(mode="json"), "origin": t.key} for si in t.starting_items]
        for name in ProgressionDef.model_fields:
            if getattr(t.progression, name) is not None:
                progression_origin[name] = t.key
        for slot in t.slots:
            slot_origin.setdefault(slot, t.key)
        for name in CombatDef.model_fields:
            if name == "damage_hooks":
                hooks += [{"expr": h, "origin": t.key} for h in t.combat.damage_hooks]
            elif getattr(t.combat, name) is not None:
                combat_origin[name] = t.key
    top = chain[-1]
    return {
        "key": eff.key,
        "label": eff.label,
        "index": eff.index,
        "parent": top.parent,
        "chain": [t.key for t in chain],
        "stats": rows("stats", eff.stats),
        "tests": rows("tests", eff.tests),
        "skills": rows("skills", eff.skills),
        "classes": rows("classes", eff.classes),
        "slots": [{"slot": s, "origin": slot_origin[s]} for s in eff.slots],
        "combat": eff.combat.model_dump(mode="json"),
        "combat_origin": combat_origin,
        "damage_hooks": hooks,
        "progression": eff.progression.model_dump(mode="json"),
        "progression_origin": progression_origin,
        "starting_items": starting,
        "class_choice": eff.class_choice,
        "class_choice_origin": next(
            (t.key for t in reversed(chain) if t.class_choice is not None), None
        ),
    }
