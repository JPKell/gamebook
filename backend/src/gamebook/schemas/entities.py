"""Series entities: enemies, items, random tables, characters, lore."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from gamebook.core.effects import Effect
from gamebook.schemas.common import In, Key, Out, Title

ItemCategory = Literal["equipment", "consumable", "key", "treasure"]
LoreType = Literal["location", "faction", "history", "glossary", "other"]


class _ScopedOut(Out):
    id: str
    series_id: str
    #: None = shared across the series.
    book_id: str | None
    key: str
    name: str
    updated_at: datetime


# ── enemies ──────────────────────────────────────────────────────────────


class LootEntry(In):
    item: Key
    qty: int = Field(default=1, ge=1)


class EnemyAbility(In):
    name: str
    description: str = ""


class EnemyFields(In):
    description: str | None = None
    tags: list[str] | None = None
    default_level: int | None = Field(default=None, ge=1)
    #: stat key → gbx formula of ``level``
    stat_formulas: dict[str, str] | None = None
    abilities: list[EnemyAbility] | None = None
    loot: list[LootEntry] | None = None
    lore_entry_id: str | None = None


class EnemyCreate(EnemyFields):
    name: Title
    key: Key | None = None
    book_id: str | None = None


class EnemyUpdate(EnemyFields):
    name: Title | None = None
    key: Key | None = None
    book_id: str | None = None


class EnemyOut(_ScopedOut):
    description: str
    tags: list[str]
    default_level: int
    stat_formulas: dict[str, str]
    abilities: list[EnemyAbility]
    loot: list[LootEntry]
    lore_entry_id: str | None


# ── items ────────────────────────────────────────────────────────────────


class ItemModifier(In):
    stat: Key
    amount: str
    min_tier: str | None = None


class ItemFields(In):
    description: str | None = None
    category: ItemCategory | None = None
    slot: str | None = None
    stackable: bool | None = None
    max_stack: int | None = Field(default=None, ge=1)
    value: int | None = Field(default=None, ge=0)
    uses: int | None = Field(default=None, ge=1)
    modifiers: list[ItemModifier] | None = None
    use_effects: list[Effect] | None = None


class ItemCreate(ItemFields):
    name: Title
    key: Key | None = None
    book_id: str | None = None


class ItemUpdate(ItemFields):
    name: Title | None = None
    key: Key | None = None
    book_id: str | None = None


class ItemOut(_ScopedOut):
    description: str
    category: ItemCategory
    slot: str | None
    stackable: bool
    max_stack: int | None
    value: int
    uses: int | None
    modifiers: list[ItemModifier]
    use_effects: list[Effect]


# ── random tables ────────────────────────────────────────────────────────


class TableEnemy(In):
    enemy: Key
    level: int = Field(default=1, ge=1)
    count: int = Field(default=1, ge=1)


class TableEntryIn(In):
    lo: int
    hi: int
    kind: Literal["enemies", "item", "gold", "nothing"] = "nothing"
    enemies: list[TableEnemy] = Field(default_factory=list)
    item: Key | None = None
    qty: int = Field(default=1, ge=1)
    amount: str | None = None
    note: str = ""


class TableFields(In):
    description: str | None = None
    dice: str | None = None
    entries: list[TableEntryIn] | None = None


class TableCreate(TableFields):
    name: Title
    key: Key | None = None
    book_id: str | None = None


class TableUpdate(TableFields):
    name: Title | None = None
    key: Key | None = None
    book_id: str | None = None


class TableOut(_ScopedOut):
    description: str
    dice: str
    entries: list[TableEntryIn]


# ── lore ─────────────────────────────────────────────────────────────────


class Relationship(In):
    character: Key
    kind: str
    notes: str = ""


class CharacterFields(In):
    role: str | None = None
    appearance: str | None = None
    voice: str | None = None
    motivations: str | None = None
    secrets: str | None = None
    notes: str | None = None
    relationships: list[Relationship] | None = None


class CharacterCreate(CharacterFields):
    name: Title
    key: Key | None = None
    book_id: str | None = None


class CharacterUpdate(CharacterFields):
    name: Title | None = None
    key: Key | None = None
    book_id: str | None = None


class CharacterOut(_ScopedOut):
    role: str
    appearance: str
    voice: str
    motivations: str
    secrets: str
    notes: str
    relationships: list[Relationship]


class LoreFields(In):
    type: LoreType | None = None
    body: str | None = None
    fields: dict[str, str] | None = None


class LoreCreate(LoreFields):
    name: Title
    key: Key | None = None
    book_id: str | None = None


class LoreUpdate(LoreFields):
    name: Title | None = None
    key: Key | None = None
    book_id: str | None = None


class LoreOut(_ScopedOut):
    type: LoreType
    body: str
    fields: dict[str, str]
