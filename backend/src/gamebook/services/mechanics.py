"""Mechanics designer support and the combat lab."""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.core import gbx
from gamebook.core.analysis import Problem, validate_rule_system
from gamebook.core.engine import LabEnemy, LabError, level_sweep, simulate
from gamebook.core.engine.combat import enemy_stats
from gamebook.core.gbx.scope import Context, ScopeInputs, scope_for
from gamebook.core.rules import RuleSystemDef, TierError, effective_tier, tier_view
from gamebook.db.models import Enemy, RuleSystem, Series
from gamebook.schemas.mechanics import (
    Distribution,
    EnemyLevelsOut,
    LabEnemyOut,
    LabIn,
    LabOut,
    LabPlayerIn,
    LevelRow,
    SweepIn,
    SweepOut,
    SweepPointOut,
    TierLevels,
    TierView,
)
from gamebook.services.common import require
from gamebook.services.errors import InvalidError


def definition(rs: RuleSystem) -> RuleSystemDef:
    try:
        return RuleSystemDef.model_validate(rs.definition)
    except ValidationError as exc:
        raise InvalidError(f"Stored rule system is invalid: {exc.error_count()} error(s)") from exc


def get_tier_view(session: Session, rule_system_id: str, tier: str) -> TierView:
    system = definition(require(session, RuleSystem, rule_system_id))
    try:
        return TierView.model_validate(tier_view(system, tier))
    except TierError as exc:
        raise InvalidError(str(exc), field="tier") from exc


def rule_problems(session: Session, rule_system_id: str) -> list[Problem]:
    return validate_rule_system(definition(require(session, RuleSystem, rule_system_id)))


def _system(session: Session, series_id: str, rule_system_id: str | None) -> RuleSystemDef:
    require(session, Series, series_id)
    rs: RuleSystem | None
    if rule_system_id is not None:
        rs = require(session, RuleSystem, rule_system_id)
        if rs.series_id != series_id:
            raise InvalidError("That rule system belongs to another series", field="rule_system_id")
    else:
        rs = session.scalar(
            select(RuleSystem).where(RuleSystem.series_id == series_id, RuleSystem.is_active)
        )
    if rs is None:
        raise InvalidError("The series has no active rule system")
    return definition(rs)


def _enemy(session: Session, series_id: str, enemy_id: str) -> Enemy:
    enemy = require(session, Enemy, enemy_id)
    if enemy.series_id != series_id:
        raise InvalidError("That enemy belongs to another series", field="enemy_id")
    return enemy


def _player(p: LabPlayerIn) -> dict[str, int] | None:
    return dict(p.stats) if p.mode == "fixed" else None


def run_lab(session: Session, series_id: str, data: LabIn) -> LabOut:
    system = _system(session, series_id, data.rule_system_id)
    try:
        eff = effective_tier(system, data.tier)
    except TierError as exc:
        raise InvalidError(str(exc), field="tier") from exc
    foes: list[LabEnemy] = []
    described: list[LabEnemyOut] = []
    for e in data.enemies:
        if e.enemy_id is not None:
            enemy = _enemy(session, series_id, e.enemy_id)
            stats = enemy_stats(
                enemy.stat_formulas, e.level, eff.enemy_stats(), system.tier_keys(), data.tier
            )
            name = enemy.name
        else:
            stats = {k: (e.stats or {}).get(k, 0) for k in eff.enemy_stats()}
            name = e.name
        foes.append(LabEnemy(name, stats, e.count))
        described.append(LabEnemyOut(name=name, level=e.level, count=e.count, stats=stats))
    try:
        result = simulate(
            system,
            data.tier,
            foes,
            runs=data.runs,
            seed=data.seed,
            player_stats=_player(data.player),
            simultaneous=data.simultaneous,
        )
    except LabError as exc:
        raise InvalidError(str(exc)) from exc
    summary = result.summary()
    rounds = summary["rounds"]
    damage = summary["damage_taken"]
    assert isinstance(rounds, dict)
    assert isinstance(damage, dict)
    return LabOut(
        runs=result.runs,
        wins=result.wins,
        losses=result.losses,
        stalemates=result.stalemates,
        win_rate=round(result.win_rate, 4),
        damage_stat=result.damage_stat,
        rounds=Distribution.model_validate(rounds),
        damage_taken=Distribution.model_validate(damage),
        remaining_on_win_mean=round(result._mean(result.remaining_on_win), 2),
        truncated=result.truncated,
        enemies=described,
    )


def run_sweep(session: Session, series_id: str, data: SweepIn) -> SweepOut:
    system = _system(session, series_id, data.rule_system_id)
    if data.enemy_id is not None:
        enemy = _enemy(session, series_id, data.enemy_id)
        name, formulas = enemy.name, dict(enemy.stat_formulas)
    else:
        name, formulas = data.name, dict(data.formulas or {})
    try:
        points = level_sweep(
            system,
            data.tier,
            name,
            formulas,
            range(data.level_from, data.level_to + 1),
            count=data.count,
            runs=data.runs,
            seed=data.seed,
            player_stats=_player(data.player),
        )
    except (LabError, TierError) as exc:
        raise InvalidError(str(exc)) from exc
    return SweepOut(
        name=name, points=[SweepPointOut.model_validate(p, from_attributes=True) for p in points]
    )


def enemy_levels(session: Session, enemy_id: str, level_from: int, level_to: int) -> EnemyLevelsOut:
    """An enemy's stats at each level, for every tier of the active rule system."""
    enemy = require(session, Enemy, enemy_id)
    system = _system(session, enemy.series_id, None)
    keys = system.tier_keys()
    errors: dict[str, str] = {}
    all_stats: set[str] = set()
    tiers: list[TierLevels] = []
    for t in system.tiers:
        try:
            eff = effective_tier(system, t.key)
        except TierError:
            continue
        stats = sorted(eff.enemy_stats())
        all_stats.update(stats)
        rows = [
            LevelRow(
                level=lv, stats=enemy_stats(enemy.stat_formulas, lv, frozenset(stats), keys, t.key)
            )
            for lv in range(level_from, level_to + 1)
        ]
        tiers.append(
            TierLevels(
                key=t.key,
                label=t.label,
                stats=stats,
                missing=[s for s in stats if not enemy.stat_formulas.get(s, "").strip()],
                rows=rows,
            )
        )
    scope = scope_for(Context.ENEMY_FORMULA, ScopeInputs(tiers=keys))
    for stat, src in sorted(enemy.stat_formulas.items()):
        _, diags = gbx.check_source(src, scope)
        bad = next((d for d in diags if d.severity == "error"), None)
        if bad is not None:
            errors[stat] = bad.message
    return EnemyLevelsOut(enemy_id=enemy.id, tiers=tiers, errors=errors)
