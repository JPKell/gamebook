"""Mechanics designer support and the combat lab."""

from fastapi import APIRouter

from gamebook.api.deps import SessionDep
from gamebook.schemas.analysis import ProblemCounts, ProblemOut, ProblemsOut
from gamebook.schemas.mechanics import LabIn, LabOut, SweepIn, SweepOut, TierView
from gamebook.services import mechanics as svc

router = APIRouter(tags=["mechanics"])


@router.get("/rule-systems/{rule_system_id}/tiers/{tier}", response_model=TierView)
def get_tier_view(rule_system_id: str, tier: str, session: SessionDep) -> TierView:
    """A tier merged with its ancestors, with where each part comes from."""
    return svc.get_tier_view(session, rule_system_id, tier)


@router.get("/rule-systems/{rule_system_id}/problems", response_model=ProblemsOut)
def get_rule_system_problems(rule_system_id: str, session: SessionDep) -> ProblemsOut:
    problems = svc.rule_problems(session, rule_system_id)
    return ProblemsOut(
        counts=ProblemCounts(
            errors=sum(p.severity == "error" for p in problems),
            warnings=sum(p.severity == "warning" for p in problems),
            info=sum(p.severity == "info" for p in problems),
        ),
        problems=[ProblemOut.model_validate(p) for p in problems],
    )


@router.post("/series/{series_id}/combat-lab", response_model=LabOut)
def run_combat_lab(series_id: str, data: LabIn, session: SessionDep) -> LabOut:
    """Monte Carlo fights: win rate, rounds and damage distributions."""
    return svc.run_lab(session, series_id, data)


@router.post("/series/{series_id}/combat-lab/sweep", response_model=SweepOut)
def run_combat_sweep(series_id: str, data: SweepIn, session: SessionDep) -> SweepOut:
    """Win rate against one enemy across a range of levels."""
    return svc.run_sweep(session, series_id, data)
