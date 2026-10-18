"""Combat lab: Monte Carlo fights to tune enemies and rules (no book needed)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from gamebook.core import gbx
from gamebook.core.engine.combat import (
    MAX_ROUNDS,
    CombatRules,
    enemies_defeated,
    enemy_stats,
    fight_round,
    player_defeated,
)
from gamebook.core.engine.env import GameEnv, compiled_int, no_refs
from gamebook.core.engine.state import Combatant
from gamebook.core.rules.schema import RuleSystemDef, effective_tier

MAX_RUNS = 20_000
#: Cap on fighter-rounds per request (each costs a few µs); results report truncation.
MAX_WORK = 1_000_000


class LabError(ValueError):
    pass


@dataclass(frozen=True)
class LabEnemy:
    name: str
    stats: Mapping[str, int]
    count: int = 1


@dataclass
class LabResult:
    runs: int
    wins: int = 0
    losses: int = 0
    stalemates: int = 0
    rounds: Counter[int] = field(default_factory=Counter)
    #: Player's damage-stat loss per fight.
    damage_taken: Counter[int] = field(default_factory=Counter)
    #: Player's remaining damage stat in fights they won.
    remaining_on_win: Counter[int] = field(default_factory=Counter)
    damage_stat: str = ""
    #: True when the work budget ran out before all requested runs finished.
    truncated: bool = False

    @property
    def win_rate(self) -> float:
        return self.wins / self.runs if self.runs else 0.0

    @staticmethod
    def _mean(c: Counter[int]) -> float:
        n = sum(c.values())
        return sum(k * v for k, v in c.items()) / n if n else 0.0

    @staticmethod
    def _percentile(c: Counter[int], q: float) -> int:
        n = sum(c.values())
        if not n:
            return 0
        seen = 0
        for k in sorted(c):
            seen += c[k]
            if seen >= q * n:
                return k
        return max(c)

    def summary(self) -> dict[str, object]:
        return {
            "runs": self.runs,
            "wins": self.wins,
            "losses": self.losses,
            "stalemates": self.stalemates,
            "win_rate": round(self.win_rate, 4),
            "damage_stat": self.damage_stat,
            "rounds": {
                "mean": round(self._mean(self.rounds), 2),
                "p50": self._percentile(self.rounds, 0.5),
                "p90": self._percentile(self.rounds, 0.9),
                "histogram": dict(sorted(self.rounds.items())),
            },
            "damage_taken": {
                "mean": round(self._mean(self.damage_taken), 2),
                "p90": self._percentile(self.damage_taken, 0.9),
                "histogram": dict(sorted(self.damage_taken.items())),
            },
            "remaining_on_win": {"mean": round(self._mean(self.remaining_on_win), 2)},
            "truncated": self.truncated,
        }


def _rules(system: RuleSystemDef, tier: str) -> tuple[CombatRules, GameEnv, frozenset[str]]:
    eff = effective_tier(system, tier)
    try:
        rules = CombatRules.from_tier(eff)
    except gbx.GbxSyntaxError as exc:
        raise LabError(f"The {eff.label} tier's combat rules don't parse: {exc}") from exc
    if rules is None:
        raise LabError(f"The {eff.label} tier has no complete combat procedure")
    return rules, GameEnv(system.tier_keys(), tier, lambda _: 0, no_refs), eff.player_stats()


def _roll_player(
    system: RuleSystemDef, tier: str, env: GameEnv, rng: gbx.SeededRng
) -> dict[str, int]:
    eff = effective_tier(system, tier)
    return {
        k: compiled_int(s.initial)(env, rng)
        for k, s in eff.stats.items()
        if "player" in s.applies_to
    }


def simulate(
    system: RuleSystemDef,
    tier: str,
    enemies: Sequence[LabEnemy],
    *,
    runs: int = 1000,
    seed: int = 0,
    player_stats: Mapping[str, int] | None = None,
    simultaneous: bool | None = None,
    max_work: int = MAX_WORK,
) -> LabResult:
    """Fight ``enemies`` ``runs`` times. Player stats are rolled each run unless fixed.

    Stops early (``truncated``) once ``max_work`` fighter-rounds have been spent.
    Content errors in the rules raise ``LabError``.
    """
    try:
        return _simulate(system, tier, enemies, runs, seed, player_stats, simultaneous, max_work)
    except (gbx.GbxSyntaxError, gbx.GbxEvalError) as exc:
        raise LabError(f"The rules failed during a fight: {exc}") from exc


def _simulate(
    system: RuleSystemDef,
    tier: str,
    enemies: Sequence[LabEnemy],
    runs: int,
    seed: int,
    player_stats: Mapping[str, int] | None,
    simultaneous: bool | None,
    max_work: int,
) -> LabResult:
    if not 1 <= runs <= MAX_RUNS:
        raise LabError(f"Runs must be between 1 and {MAX_RUNS}")
    if not enemies:
        raise LabError("Choose at least one enemy")
    rules, env, player_keys = _rules(system, tier)
    rng = gbx.SeededRng(seed)
    sim = rules.simultaneous_default if simultaneous is None else simultaneous
    result = LabResult(runs=0, damage_stat=rules.damage_stat)
    work = 0
    fighters = 1 + sum(e.count for e in enemies)
    for _ in range(runs):
        if work >= max_work:
            result.truncated = True
            break
        rng.history.clear()  # only the current round's dice matter
        player = (
            dict(player_stats) if player_stats is not None else _roll_player(system, tier, env, rng)
        )
        for key in player_keys:
            player.setdefault(key, 0)
        foes = [
            Combatant(key=f"{e.name}#{i}", name=e.name, stats=dict(e.stats))
            for e in enemies
            for i in range(e.count)
        ]
        start = player.get(rules.damage_stat, 0)
        rounds = 0
        while True:
            rounds += 1
            work += fighters if sim else 2
            rng.history.clear()
            fight_round(rules, env, rng, player, foes, sim, rounds)
            if player_defeated(rules, player):
                result.losses += 1
                break
            if enemies_defeated(rules, foes):
                result.wins += 1
                result.remaining_on_win[player.get(rules.damage_stat, 0)] += 1
                break
            if rounds >= MAX_ROUNDS:
                result.stalemates += 1
                break
        result.runs += 1
        result.rounds[rounds] += 1
        result.damage_taken[start - player.get(rules.damage_stat, 0)] += 1
    return result


@dataclass(frozen=True)
class SweepPoint:
    level: int
    enemy: dict[str, int]
    win_rate: float
    rounds_mean: float
    damage_taken_mean: float


def level_sweep(
    system: RuleSystemDef,
    tier: str,
    name: str,
    formulas: Mapping[str, str],
    levels: Sequence[int],
    *,
    count: int = 1,
    runs: int = 500,
    seed: int = 0,
    player_stats: Mapping[str, int] | None = None,
) -> list[SweepPoint]:
    """Win rate against an enemy across levels (same seed per level, so curves are smooth)."""
    eff = effective_tier(system, tier)
    points = []
    for level in levels:
        stats = enemy_stats(formulas, level, eff.enemy_stats(), system.tier_keys(), tier)
        r = simulate(
            system,
            tier,
            [LabEnemy(name, stats, count)],
            runs=runs,
            seed=seed,
            player_stats=player_stats,
            max_work=MAX_WORK // max(1, len(levels)),
        )
        points.append(
            SweepPoint(
                level=level,
                enemy=stats,
                win_rate=round(r.win_rate, 4),
                rounds_mean=round(LabResult._mean(r.rounds), 2),
                damage_taken_mean=round(LabResult._mean(r.damage_taken), 2),
            )
        )
    return points
