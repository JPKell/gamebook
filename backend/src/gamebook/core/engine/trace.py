"""Golden traces: (bundle, tier, seed, creation, actions) → expected events.

A trace pins down engine behaviour exactly. The Python engine is the
reference; the TypeScript runtime (Phase 11) must replay every trace to the
same events and final state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from gamebook.core.engine.bundle import from_bundle, to_bundle
from gamebook.core.engine.events import Action
from gamebook.core.engine.game import Game
from gamebook.core.model import BookSnapshot

TRACE_FORMAT = "gamebook-trace"
TRACE_VERSION = 1

Policy = Callable[[Game], Action | None]


def first_available(game: Game) -> Action | None:
    """Deterministic policy: always take the first enabled action."""
    options = game.available()
    return options[0] if options else None


def rotating(game: Game) -> Action | None:
    """Deterministic exploring policy: step N takes option N mod len(options)."""
    options = game.available()
    return options[game.state.steps % len(options)] if options else None


def record(
    book: BookSnapshot,
    tier: str,
    seed: int,
    *,
    policy: Policy = first_available,
    creation: dict[str, Any] | None = None,
    max_steps: int = 200,
) -> dict[str, Any]:
    creation = creation or {}
    game = Game(book, tier, seed)
    game.start(**creation)
    actions: list[dict[str, Any]] = []
    while not game.state.ended and len(actions) < max_steps:
        action = policy(game)
        if action is None:
            break
        actions.append(action.to_dict())
        game.step(action)
    return {
        "format": TRACE_FORMAT,
        "version": TRACE_VERSION,
        "bundle": to_bundle(book),
        "tier": tier,
        "seed": seed,
        "creation": creation,
        "actions": actions,
        "events": [e.to_dict() for e in game.log],
        "final_state": game.state.to_dict(),
    }


def replay(trace: dict[str, Any]) -> dict[str, Any]:
    """Re-run a trace's inputs; returns ``{"events": [...], "final_state": {...}}``."""
    if trace.get("format") != TRACE_FORMAT:
        raise ValueError("Not a gamebook trace")
    game = Game(from_bundle(trace["bundle"]), trace["tier"], trace["seed"])
    game.start(**trace.get("creation", {}))
    for a in trace["actions"]:
        game.step(Action.from_dict(a))
    return {"events": [e.to_dict() for e in game.log], "final_state": game.state.to_dict()}
