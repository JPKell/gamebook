"""The combat procedure (SPEC §2.4), shared by games and the combat lab.

Each round every fighting enemy rolls attack strength against the player's.
The player damages their current target only when beating its roll; any
enemy that beats the player's roll damages the player (Fighting Fantasy style;
in "sequential" fights only the first living enemy fights). Damage starts at
``combat.damage`` and passes through ``damage_hooks`` in order, each seeing
``damage``, ``natural`` (the attacker's dice faces), ``attacker`` and ``target``.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from gamebook.core import gbx
from gamebook.core.engine.env import GameEnv, compile_expr, compiled_int
from gamebook.core.engine.events import Event
from gamebook.core.engine.state import Combatant
from gamebook.core.gbx.compiler import Number, _number_of
from gamebook.core.rules.schema import EffectiveTier

MAX_ROUNDS = 200


NumberFn = Callable[[gbx.Env, gbx.Rng | None], Number]


@dataclass(frozen=True)
class CombatRules:
    player_attack: NumberFn
    enemy_attack: NumberFn
    damage: NumberFn
    damage_stat: str
    hooks: tuple[NumberFn, ...]
    player_defeat_at: int
    enemy_defeat_at: int
    stat_min: int | None
    simultaneous_default: bool
    flee_allowed: bool

    @classmethod
    def from_tier(cls, tier: EffectiveTier) -> CombatRules | None:
        c = tier.combat
        if not (c.player_attack and c.enemy_attack and c.damage_stat):
            return None
        stat = tier.stats.get(c.damage_stat)
        defeat_at = stat.defeat_at if stat and stat.defeat_at is not None else 0

        def num(src: str) -> NumberFn:
            return _number_of(compile_expr(src), "player")

        return cls(
            player_attack=num(c.player_attack),
            enemy_attack=num(c.enemy_attack),
            damage=num(c.damage or "2"),
            damage_stat=c.damage_stat,
            hooks=tuple(num(h) for h in c.damage_hooks),
            player_defeat_at=defeat_at,
            enemy_defeat_at=defeat_at,
            stat_min=stat.min if stat else 0,
            simultaneous_default=c.multi_enemy == "simultaneous",
            flee_allowed=c.flee_allowed is not False,
        )


def _roll(fn: NumberFn, env: GameEnv, rng: gbx.SeededRng) -> tuple[int, int]:
    """(total, natural) where natural is the sum of the dice faces rolled."""
    before = len(rng.history)
    total = math.floor(fn(env, rng))
    natural = sum(sum(faces) for _, _, faces in rng.history[before:])
    return total, natural


def _damage(
    rules: CombatRules,
    env: GameEnv,
    rng: gbx.SeededRng,
    attacker: Mapping[str, int],
    target: Mapping[str, int],
    natural: int,
) -> int:
    env = env.with_(objects={"attacker": attacker, "target": target})
    amount: Number = rules.damage(env, rng)
    for hook in rules.hooks:
        amount = hook(
            env.with_(variables={"damage": Fraction(amount), "natural": Fraction(natural)}), rng
        )
    return max(0, math.floor(amount))


def _hit(stats: dict[str, int], rules: CombatRules, amount: int) -> int:
    before = stats.get(rules.damage_stat, 0)
    after = before - amount
    if rules.stat_min is not None:
        after = max(rules.stat_min, after)
    stats[rules.damage_stat] = after
    return before - after


def fight_round(
    rules: CombatRules,
    env: GameEnv,
    rng: gbx.SeededRng,
    player: dict[str, int],
    enemies: list[Combatant],
    simultaneous: bool,
    round_no: int,
) -> list[Event]:
    """Resolve one round, mutating ``player`` and enemy stats. Returns events."""
    alive = [e for e in enemies if e.stats.get(rules.damage_stat, 0) > rules.enemy_defeat_at]
    if not alive:
        return []
    fighting = alive if simultaneous else alive[:1]
    target = alive[0]
    events: list[Event] = []
    p_env = env.with_(objects={"player": player, "enemy": target.stats})
    p_total, p_natural = _roll(rules.player_attack, p_env, rng)
    for enemy in fighting:
        e_env = env.with_(objects={"player": player, "enemy": enemy.stats})
        e_total, e_natural = _roll(rules.enemy_attack, e_env, rng)
        detail: dict[str, object] = {
            "round": round_no,
            "enemy": enemy.key,
            "player_attack": p_total,
            "enemy_attack": e_total,
        }
        if enemy is target and p_total > e_total:
            dealt = _hit(
                enemy.stats, rules, _damage(rules, e_env, rng, player, enemy.stats, p_natural)
            )
            detail.update(hit="enemy", damage=dealt, remaining=enemy.stats[rules.damage_stat])
        elif e_total > p_total:
            dealt = _hit(player, rules, _damage(rules, e_env, rng, enemy.stats, player, e_natural))
            detail.update(hit="player", damage=dealt, remaining=player[rules.damage_stat])
        else:
            detail.update(hit=None)
        events.append(Event("combat_round", detail))
        if (
            enemy.stats.get(rules.damage_stat, 0) <= rules.enemy_defeat_at
            and detail.get("hit") == "enemy"
        ):
            events.append(Event("enemy_defeated", {"enemy": enemy.key}))
        if player.get(rules.damage_stat, 0) <= rules.player_defeat_at:
            break
    return events


def player_defeated(rules: CombatRules, player: Mapping[str, int]) -> bool:
    return player.get(rules.damage_stat, 0) <= rules.player_defeat_at


def enemies_defeated(rules: CombatRules, enemies: list[Combatant]) -> bool:
    return all(e.stats.get(rules.damage_stat, 0) <= rules.enemy_defeat_at for e in enemies)


def enemy_stats(
    formulas: Mapping[str, str],
    level: int,
    stats: frozenset[str],
    tiers: tuple[str, ...],
    tier: str,
) -> dict[str, int]:
    """Evaluate an enemy's stat formulas at a level (missing stats are 0)."""
    from gamebook.core.engine.env import no_refs

    env = GameEnv(tiers, tier, lambda _: 0, no_refs, {"level": Fraction(level)})
    out: dict[str, int] = {}
    for stat in sorted(stats):
        src = formulas.get(stat)
        try:
            out[stat] = compiled_int(src)(env, None) if src else 0
        except (gbx.GbxSyntaxError, gbx.GbxEvalError):
            out[stat] = 0
    return out
