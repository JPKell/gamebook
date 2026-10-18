"""Mechanics designer support and the combat lab."""

from fastapi import APIRouter, Query

from gamebook.api.deps import SessionDep
from gamebook.core.analysis import Problem
from gamebook.schemas.analysis import ProblemCounts, ProblemOut, ProblemsOut
from gamebook.schemas.mechanics import EnemyLevelsOut, LabIn, LabOut, SweepIn, SweepOut, TierView
from gamebook.services import mechanics as svc
from gamebook.services import snapshot
from gamebook.services.errors import InvalidError

router = APIRouter(tags=["mechanics"])


@router.get("/rule-systems/{rule_system_id}/tiers/{tier}", response_model=TierView)
def get_tier_view(rule_system_id: str, tier: str, session: SessionDep) -> TierView:
    """A tier merged with its ancestors, with where each part comes from."""
    return svc.get_tier_view(session, rule_system_id, tier)


@router.get("/rule-systems/{rule_system_id}/problems", response_model=ProblemsOut)
def get_rule_system_problems(rule_system_id: str, session: SessionDep) -> ProblemsOut:
    return _problems_out(svc.rule_problems(session, rule_system_id))


@router.post("/series/{series_id}/combat-lab", response_model=LabOut)
def run_combat_lab(series_id: str, data: LabIn, session: SessionDep) -> LabOut:
    """Monte Carlo fights: win rate, rounds and damage distributions."""
    return svc.run_lab(session, series_id, data)


@router.post("/series/{series_id}/combat-lab/sweep", response_model=SweepOut)
def run_combat_sweep(series_id: str, data: SweepIn, session: SessionDep) -> SweepOut:
    """Win rate against one enemy across a range of levels."""
    return svc.run_sweep(session, series_id, data)


@router.get("/enemies/{enemy_id}/levels", response_model=EnemyLevelsOut)
def get_enemy_levels(
    enemy_id: str,
    session: SessionDep,
    level_from: int = Query(default=1, ge=1, le=100),
    level_to: int = Query(default=10, ge=1, le=100),
) -> EnemyLevelsOut:
    """An enemy's stats at each level, per tier of the active rule system."""
    if level_to < level_from or level_to - level_from >= 50:
        raise InvalidError("Choose 1-50 levels, from ≤ to", field="level_to")
    return svc.enemy_levels(session, enemy_id, level_from, level_to)


@router.get("/series/{series_id}/entity-problems", response_model=ProblemsOut)
def get_entity_problems(series_id: str, session: SessionDep) -> ProblemsOut:
    """Validation of the series' enemies, items and random tables."""
    return _problems_out(snapshot.series_entity_problems(session, series_id))


def _problems_out(problems: list[Problem]) -> ProblemsOut:
    return ProblemsOut(
        counts=ProblemCounts(
            errors=sum(p.severity == "error" for p in problems),
            warnings=sum(p.severity == "warning" for p in problems),
            info=sum(p.severity == "info" for p in problems),
        ),
        problems=[ProblemOut.model_validate(p) for p in problems],
    )
