"""Immutable snapshot of one book plus the series entities it can use.

Built by the services layer from the database; consumed by validation, the
state-digest analysis and (Phase 3+) the engine. Entity references inside
expressions and effects are by key; row relations (encounters, placements,
outcome targets) are by id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from gamebook.core.effects import Effect
from gamebook.core.rules.schema import RuleSystemDef

ChoiceKind = Literal["goto", "roll", "test", "combat"]
EndingKind = Literal["victory", "death", "dead_end"]
EndingGrade = Literal["good", "neutral", "bad", "secret"]

OUTCOME_KEYS: dict[ChoiceKind, tuple[str, ...]] = {
    "goto": ("default",),
    "test": ("success", "failure"),
    "combat": ("win", "lose", "flee"),
    "roll": (),  # free-form branch keys with ranges
}


@dataclass(frozen=True)
class Outcome:
    id: str
    key: str
    target_id: str | None
    range_lo: int | None = None
    range_hi: int | None = None


@dataclass(frozen=True)
class Choice:
    id: str
    node_id: str
    label: str
    kind: ChoiceKind = "goto"
    condition: str | None = None
    min_tier: str | None = None
    effects: tuple[Effect, ...] = ()
    dice: str | None = None
    test: str | None = None
    encounter_id: str | None = None
    flee_allowed: bool = False
    outcomes: tuple[Outcome, ...] = ()


@dataclass(frozen=True)
class Variant:
    id: str
    label: str
    condition: str | None = None
    priority: int = 0


@dataclass(frozen=True)
class EncounterEnemy:
    enemy_id: str
    level: int = 1
    count: int = 1


@dataclass(frozen=True)
class Encounter:
    id: str
    label: str
    mode: Literal["fixed", "table"] = "fixed"
    fight: Literal["sequential", "simultaneous"] = "sequential"
    table_id: str | None = None
    enemies: tuple[EncounterEnemy, ...] = ()


@dataclass(frozen=True)
class Placement:
    item_id: str
    qty: int = 1


@dataclass(frozen=True)
class ShopEntry:
    item_id: str
    price: int
    stock: int | None = None


@dataclass(frozen=True)
class Node:
    id: str
    key: str
    title: str
    act_id: str
    is_act_entry: bool = False
    is_act_exit: bool = False
    ending_kind: EndingKind | None = None
    ending_grade: EndingGrade | None = None
    on_enter: tuple[Effect, ...] = ()
    variants: tuple[Variant, ...] = ()
    choices: tuple[Choice, ...] = ()
    encounters: tuple[Encounter, ...] = ()
    items: tuple[Placement, ...] = ()
    shop: tuple[ShopEntry, ...] | None = None
    section_pin: int | None = None


@dataclass(frozen=True)
class Act:
    id: str
    key: str
    title: str
    position: int


@dataclass(frozen=True)
class Entity:
    """Any series entity; ``book_id`` None means shared across the series."""

    id: str
    key: str
    name: str
    book_id: str | None = None


@dataclass(frozen=True)
class Enemy(Entity):
    stat_formulas: dict[str, str] = field(default_factory=dict)
    default_level: int = 1


@dataclass(frozen=True)
class ItemModifier:
    stat: str
    amount: str
    min_tier: str | None = None


@dataclass(frozen=True)
class Item(Entity):
    category: str = "treasure"
    modifiers: tuple[ItemModifier, ...] = ()
    use_effects: tuple[Effect, ...] = ()


@dataclass(frozen=True)
class TableEntry:
    lo: int
    hi: int
    kind: Literal["enemies", "item", "gold", "nothing"]
    enemies: tuple[tuple[str, int, int], ...] = ()  # (enemy key, level, count)
    item: str | None = None
    qty: int = 1
    amount: str | None = None  # gbx for gold


@dataclass(frozen=True)
class RandomTable(Entity):
    dice: str = "1d6"
    entries: tuple[TableEntry, ...] = ()


@dataclass(frozen=True)
class BookSnapshot:
    book_id: str
    series_id: str
    title: str
    start_node_id: str | None
    acts: tuple[Act, ...]
    nodes: tuple[Node, ...]
    rules: RuleSystemDef | None = None
    items: tuple[Item, ...] = ()
    enemies: tuple[Enemy, ...] = ()
    tables: tuple[RandomTable, ...] = ()
    characters: tuple[Entity, ...] = ()
    lore: tuple[Entity, ...] = ()
    #: Flags set anywhere in the series (any book), for "never set" checks.
    series_flags_set: frozenset[str] = frozenset()

    def node(self, node_id: str) -> Node | None:
        return self._nodes_by_id().get(node_id)

    def _nodes_by_id(self) -> dict[str, Node]:
        cache: dict[str, Node] | None = self.__dict__.get("_node_cache")
        if cache is None:
            cache = {n.id: n for n in self.nodes}
            object.__setattr__(self, "_node_cache", cache)
        return cache

    def act_index(self) -> dict[str, int]:
        ordered = sorted(self.acts, key=lambda a: a.position)
        return {a.id: i for i, a in enumerate(ordered)}

    def available(self, entity: Entity) -> bool:
        return entity.book_id is None or entity.book_id == self.book_id
