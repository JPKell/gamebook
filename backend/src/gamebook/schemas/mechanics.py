"""Mechanics designer and combat lab."""

from typing import Literal

from pydantic import Field, model_validator

from gamebook.core.rules import (
    ClassDef,
    CombatDef,
    ProgressionDef,
    SkillDef,
    StartingItem,
    StatDef,
    TestDef,
)
from gamebook.schemas.common import In, Out


class Provenance(Out):
    #: First tier that defines this key.
    introduced: str
    #: Tier whose definition is in effect (differs from ``introduced`` when overridden).
    origin: str


class StatView(StatDef, Provenance):
    pass


class TestView(TestDef, Provenance):
    pass


class SkillView(SkillDef, Provenance):
    pass


class ClassView(ClassDef, Provenance):
    pass


class SlotView(Out):
    slot: str
    origin: str


class StartingItemView(StartingItem, Out):
    #: Tier that gives it.
    origin: str


class HookView(Out):
    expr: str
    origin: str


class TierView(Out):
    key: str
    label: str
    index: int
    parent: str | None
    #: Root-first tier keys this tier inherits from (including itself).
    chain: list[str]
    stats: list[StatView]
    tests: list[TestView]
    skills: list[SkillView]
    classes: list[ClassView]
    slots: list[SlotView]
    combat: CombatDef
    #: Combat field → tier that set it.
    combat_origin: dict[str, str]
    damage_hooks: list[HookView]
    progression: ProgressionDef
    #: Progression field → tier that set it.
    progression_origin: dict[str, str]
    #: Every tier's starting items, root first.
    starting_items: list[StartingItemView]
    #: When readers pick a class: "start" (creation) or "story" (a choose-class effect).
    class_choice: Literal["start", "story"]
    class_choice_origin: str | None


# ── combat lab ───────────────────────────────────────────────────────────


class LabEnemyIn(In):
    """An enemy from the series (by id, at a level) or ad-hoc stats."""

    enemy_id: str | None = None
    name: str = "Enemy"
    stats: dict[str, int] | None = None
    level: int = Field(default=1, ge=1, le=100)
    count: int = Field(default=1, ge=1, le=10)

    @model_validator(mode="after")
    def _one_source(self) -> "LabEnemyIn":
        if (self.enemy_id is None) == (self.stats is None):
            raise ValueError("Give either enemy_id or stats")
        return self


class LabPlayerIn(In):
    mode: Literal["rolled", "fixed"] = "rolled"
    stats: dict[str, int] = Field(default_factory=dict)


class LabIn(In):
    rule_system_id: str | None = Field(default=None, description="Defaults to the active system")
    tier: str
    enemies: list[LabEnemyIn] = Field(min_length=1, max_length=10)
    player: LabPlayerIn = Field(default_factory=LabPlayerIn)
    runs: int = Field(default=2000, ge=1, le=20_000)
    seed: int = Field(default=1, ge=0)
    simultaneous: bool | None = None

    @model_validator(mode="after")
    def _total_enemies(self) -> "LabIn":
        if sum(e.count for e in self.enemies) > 10:
            raise ValueError("At most 10 enemies in one fight")
        return self


class LabEnemyOut(Out):
    name: str
    level: int
    count: int
    stats: dict[str, int]


class Distribution(Out):
    mean: float
    p50: int | None = None
    p90: int
    histogram: dict[int, int]


class LabOut(Out):
    runs: int
    wins: int
    losses: int
    stalemates: int
    win_rate: float
    damage_stat: str
    rounds: Distribution
    damage_taken: Distribution
    remaining_on_win_mean: float
    #: The work budget ran out first; ``runs`` is how many fights completed.
    truncated: bool
    enemies: list[LabEnemyOut]


class SweepIn(In):
    rule_system_id: str | None = None
    tier: str
    enemy_id: str | None = None
    name: str = "Enemy"
    formulas: dict[str, str] | None = Field(default=None, description="Ad-hoc formulas of `level`")
    level_from: int = Field(default=1, ge=1, le=100)
    level_to: int = Field(default=10, ge=1, le=100)
    count: int = Field(default=1, ge=1, le=10)
    player: LabPlayerIn = Field(default_factory=LabPlayerIn)
    runs: int = Field(default=500, ge=10, le=5000)
    seed: int = Field(default=1, ge=0)

    @model_validator(mode="after")
    def _check(self) -> "SweepIn":
        if (self.enemy_id is None) == (self.formulas is None):
            raise ValueError("Give either enemy_id or formulas")
        if self.level_to < self.level_from:
            raise ValueError("level_to must not be below level_from")
        if (self.level_to - self.level_from + 1) * self.runs > 30_000:
            raise ValueError("Too much work: levels x runs must be at most 30,000")
        return self


class SweepPointOut(Out):
    level: int
    enemy: dict[str, int]
    win_rate: float
    rounds_mean: float
    damage_taken_mean: float


class SweepOut(Out):
    name: str
    points: list[SweepPointOut]


# ── enemy level tables ───────────────────────────────────────────────────


class LevelRow(Out):
    level: int
    stats: dict[str, int]


class TierLevels(Out):
    key: str
    label: str
    #: Enemy stats active at this tier.
    stats: list[str]
    #: Active stats with no formula (they count as 0).
    missing: list[str]
    rows: list[LevelRow]


class EnemyLevelsOut(Out):
    enemy_id: str
    tiers: list[TierLevels]
    #: stat → first error in its formula.
    errors: dict[str, str]
