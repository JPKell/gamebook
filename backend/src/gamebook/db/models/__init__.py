"""ORM models. Every model module is imported here so ``Base.metadata`` is
complete for Alembic autogenerate and tests."""

from gamebook.db.base import Base
from gamebook.db.models.book import Act, BeatNode, Book, StoryBeat
from gamebook.db.models.entities import Character, Enemy, Item, LoreEntry, RandomTable
from gamebook.db.models.history import HistoryEntry
from gamebook.db.models.node import (
    Choice,
    ChoiceOutcome,
    Encounter,
    EncounterEnemy,
    Node,
    NodeCharacter,
    NodeItem,
    ShopItem,
    TextVariant,
)
from gamebook.db.models.playtest import Job, PlaytestBatch, PlaytestRun
from gamebook.db.models.refs import RefIndex
from gamebook.db.models.series import RuleSystem, Series

__all__ = [
    "Act",
    "Base",
    "BeatNode",
    "Book",
    "Character",
    "Choice",
    "ChoiceOutcome",
    "Encounter",
    "EncounterEnemy",
    "Enemy",
    "HistoryEntry",
    "Item",
    "Job",
    "LoreEntry",
    "Node",
    "NodeCharacter",
    "NodeItem",
    "PlaytestBatch",
    "PlaytestRun",
    "RandomTable",
    "RefIndex",
    "RuleSystem",
    "Series",
    "ShopItem",
    "StoryBeat",
    "TextVariant",
]
