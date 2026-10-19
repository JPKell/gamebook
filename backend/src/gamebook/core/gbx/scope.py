"""What names an expression may use, per authoring context.

A :class:`Scope` is built by the caller (services layer) from the active rule
system and the series' entities. The checker validates against it; the
reference extractor uses it to classify names.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Literal

GbxType = Literal["number", "bool", "tier"]


class RefKind(StrEnum):
    ITEM = "item"
    FLAG = "flag"
    SKILL = "skill"
    CLASS = "class"
    NODE = "node"
    STAT = "stat"
    TIER = "tier"


@dataclass(frozen=True, slots=True)
class RefFunction:
    """A function whose single argument is a key of some kind, e.g. ``has(rope)``."""

    name: str
    kind: RefKind
    returns: GbxType
    printable: bool = True


REF_FUNCTIONS: Mapping[str, RefFunction] = {
    f.name: f
    for f in (
        RefFunction("has", RefKind.ITEM, "bool"),
        RefFunction("count", RefKind.ITEM, "number"),
        RefFunction("equipped", RefKind.ITEM, "bool"),
        RefFunction("flag", RefKind.FLAG, "bool"),
        RefFunction("skill", RefKind.SKILL, "bool"),
        RefFunction("class", RefKind.CLASS, "bool"),
        # Needs a print strategy (tick boxes / split sections) — see SPEC §6.3.
        RefFunction("visits", RefKind.NODE, "number", printable=False),
    )
}

# name -> (min args, max args or None)
MATH_FUNCTIONS: Mapping[str, tuple[int, int | None]] = {
    "min": (2, None),
    "max": (2, None),
    "floor": (1, 1),
    "ceil": (1, 1),
    "round": (1, 1),
    "abs": (1, 1),
    "clamp": (3, 3),
}

ROUNDING_FUNCTIONS = frozenset({"floor", "ceil", "round"})


@dataclass(frozen=True, slots=True)
class Scope:
    """Names available to an expression.

    ``objects`` maps an object name (``player``, ``enemy``, ``target``…) to its
    stat keys. ``bare_object`` lets bare stat names (``GOLD``) mean that object's
    stat. ``refs`` maps a reference kind to the known keys, or ``None`` to accept
    any key (e.g. flags/codewords, which are declared by use).
    """

    expected: GbxType = "number"
    variables: Mapping[str, GbxType] = field(default_factory=dict)
    objects: Mapping[str, frozenset[str]] = field(default_factory=dict)
    bare_object: str | None = None
    tiers: tuple[str, ...] = ()
    refs: Mapping[RefKind, frozenset[str] | None] = field(default_factory=dict)
    allow_dice: bool = True
    require_integer: bool = False

    def with_(self, **changes: object) -> Scope:
        return replace(self, **changes)  # type: ignore[arg-type]


class Context(StrEnum):
    """Standard authoring contexts. ``scope_for`` builds a Scope for each."""

    CONDITION = "condition"  # choice / variant gating — bool, deterministic
    AMOUNT = "amount"  # effect amounts — number, dice allowed
    ROLL = "roll"  # roll-choice dice — number
    TEST_ROLL = "test_roll"  # rule-system test roll
    TEST_SUCCESS = "test_success"  # rule-system test success — bool, var `roll`
    ENEMY_FORMULA = "enemy_formula"  # stat as function of `level` — number, no dice
    STAT_INITIAL = "stat_initial"  # character creation — number, dice allowed
    COMBAT_ATTACK = "combat_attack"  # attack strength — number
    COMBAT_DAMAGE = "combat_damage"  # damage hook — number, vars damage/natural
    XP_AWARD = "xp_award"  # XP per enemy — number, vars enemy_level/level
    XP_TO_NEXT = "xp_to_next"  # XP for the next level — number of `level`, no dice
    STAT_BONUS = "stat_bonus"  # class / level-up bonus — number, var level


@dataclass(frozen=True, slots=True)
class ScopeInputs:
    """Everything needed to build the standard scopes for one tier."""

    player_stats: frozenset[str] = frozenset()
    enemy_stats: frozenset[str] = frozenset()
    tiers: tuple[str, ...] = ()
    items: frozenset[str] | None = None
    skills: frozenset[str] | None = None
    classes: frozenset[str] | None = None
    nodes: frozenset[str] | None = None


def scope_for(context: Context, inputs: ScopeInputs) -> Scope:
    refs: dict[RefKind, frozenset[str] | None] = {
        RefKind.ITEM: inputs.items,
        RefKind.FLAG: None,
        RefKind.SKILL: inputs.skills,
        RefKind.CLASS: inputs.classes,
        RefKind.NODE: inputs.nodes,
    }
    player = {"player": inputs.player_stats}
    base = Scope(tiers=inputs.tiers, refs=refs)
    combatants = {
        "player": inputs.player_stats,
        "enemy": inputs.enemy_stats,
        # In combat hooks the attacker/target may be either side, so only stats
        # both sides have are safe to use.
        "attacker": inputs.player_stats & inputs.enemy_stats,
        "target": inputs.player_stats & inputs.enemy_stats,
    }
    match context:
        case Context.CONDITION:
            return base.with_(
                expected="bool", objects=player, bare_object="player", allow_dice=False
            )
        case Context.AMOUNT:
            return base.with_(objects=player, bare_object="player", require_integer=True)
        case Context.ROLL | Context.TEST_ROLL:
            return base.with_(objects=player, bare_object="player", require_integer=True)
        case Context.TEST_SUCCESS:
            return base.with_(
                expected="bool",
                objects=player,
                bare_object="player",
                variables={"roll": "number"},
                allow_dice=False,
            )
        case Context.ENEMY_FORMULA:
            return Scope(
                expected="number",
                variables={"level": "number"},
                tiers=inputs.tiers,
                allow_dice=False,
                require_integer=True,
            )
        case Context.STAT_INITIAL:
            return Scope(expected="number", tiers=inputs.tiers, require_integer=True)
        case Context.COMBAT_ATTACK:
            return base.with_(objects=combatants, require_integer=True)
        case Context.COMBAT_DAMAGE:
            return base.with_(
                objects=combatants,
                variables={"damage": "number", "natural": "number"},
                require_integer=True,
            )
        case Context.XP_AWARD:
            return base.with_(
                objects=player,
                bare_object="player",
                variables={"enemy_level": "number", "level": "number"},
                require_integer=True,
            )
        case Context.XP_TO_NEXT:
            return Scope(
                expected="number",
                variables={"level": "number"},
                tiers=inputs.tiers,
                allow_dice=False,
                require_integer=True,
            )
        case Context.STAT_BONUS:
            return base.with_(
                objects=player,
                bare_object="player",
                variables={"level": "number"},
                require_integer=True,
            )
    raise ValueError(context)
