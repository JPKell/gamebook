"""Deterministic gamebook engine (SPEC §2, ADR 0002).

``Game`` plays a ``BookSnapshot`` at one tier from a seed; ``lab`` runs
combat Monte Carlo; ``bundle``/``trace`` serialise books and golden traces.
"""

from gamebook.core.engine.bundle import from_bundle, to_bundle
from gamebook.core.engine.events import Action, Event
from gamebook.core.engine.game import Game, GameError
from gamebook.core.engine.lab import LabEnemy, LabError, LabResult, level_sweep, simulate
from gamebook.core.engine.state import Combatant, CombatState, GameState
from gamebook.core.engine.trace import first_available, record, replay, rotating

__all__ = [
    "Action",
    "CombatState",
    "Combatant",
    "Event",
    "Game",
    "GameError",
    "GameState",
    "LabEnemy",
    "LabError",
    "LabResult",
    "first_available",
    "from_bundle",
    "level_sweep",
    "record",
    "replay",
    "rotating",
    "simulate",
    "to_bundle",
]
