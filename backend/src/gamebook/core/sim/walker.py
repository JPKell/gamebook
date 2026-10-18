"""Coverage walker: which nodes and endings can a reader actually reach?

A bounded breadth-first search over game states. Every choice, pickup, purchase
and equip is tried from every distinct state; steps that rolled dice are
re-run with several dice seeds so different outcomes are found. Fights are
resolved as one move (attack until it's over), with fleeing as a separate move.

States are deduplicated on what conditions can see: node, items, equipment,
codewords, skills, class, once-only pickups/effects already used, visit counts
of nodes that conditions ask about (``visits(x)``, capped at ``VISIT_CAP``),
and money up to the highest shop price (so saving up for a purchase is
explored, but endless grinding isn't). Other stat values are ignored, so the
walk is an under-approximation for books that gate on precise stat thresholds. It is
bounded by ``max_states`` and reports when it stopped early.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from gamebook.core.engine.events import Action, Event
from gamebook.core.engine.game import Game
from gamebook.core.model import BookSnapshot

#: Events that mean a step drew dice (so other seeds may differ).
_RANDOM = frozenset({"roll", "combat_round", "table", "test"})
_MOVES = frozenset({"choose", "take", "buy", "sell", "equip", "use"})
#: Visit counts above this look the same to the walker.
VISIT_CAP = 4
_VISITS = re.compile(r"\bvisits\(\s*([A-Za-z][A-Za-z0-9_]*)\s*\)")


@dataclass
class WalkResult:
    reached: set[str] = field(default_factory=set)
    endings: dict[str, set[str]] = field(default_factory=dict)  # node id → ending kinds
    #: Ending kinds reached without an ending node (e.g. defeated, stuck).
    other_endings: set[str] = field(default_factory=set)
    states: int = 0
    truncated: bool = False


def _watched_visits(book: BookSnapshot) -> frozenset[str]:
    """Node keys whose visit counts some condition can see."""
    sources: list[str] = []
    for n in book.nodes:
        sources += [v.condition or "" for v in n.variants]
        sources += [c.condition or "" for c in n.choices]
    return frozenset(m for src in sources for m in _VISITS.findall(src))


def _signature(g: Game, money_cap: int, watched: frozenset[str]) -> tuple[object, ...]:
    s = g.state
    money = min(s.stats.get(g.currency, 0), money_cap) if g.currency else 0
    return (
        money,
        s.node_id,
        s.combat.choice_id if s.combat else None,
        tuple(sorted((k, min(v, VISIT_CAP)) for k, v in s.visits.items() if k in watched)),
        tuple(sorted(s.fired)),
        s.ended,
        tuple(sorted(k for k, v in s.items.items() if v > 0)),
        tuple(sorted(s.equipped.items())),
        tuple(sorted(s.flags)),
        tuple(sorted(s.skills)),
        s.character_class,
    )


def _resolve_fight(g: Game, max_rounds: int = 200) -> list[Event]:
    events: list[Event] = []
    while g.state.combat is not None and not g.state.ended and max_rounds:
        events += g.step(Action("attack"))
        max_rounds -= 1
    return events


def _advance(g: Game, action: Action) -> list[Event]:
    """One move. A fight it starts stays open, so attack and flee are both explored."""
    if action.type == "attack":
        return _resolve_fight(g)
    return g.step(action)


def walk(
    book: BookSnapshot,
    tier: str,
    *,
    max_states: int = 20_000,
    samples: int = 4,
    seed: int = 1,
    on_progress: Callable[[int], None] | None = None,
) -> WalkResult:
    out = WalkResult()
    money_cap = max((e.price for n in book.nodes for e in n.shop or ()), default=0)
    start = Game(book, tier, seed)
    start.start()
    queue: deque[Game] = deque([start])
    watched = _watched_visits(book)
    seen = {_signature(start, money_cap, watched)}
    salt = seed
    while queue:
        g = queue.popleft()
        out.states += 1
        if on_progress is not None and out.states % 50 == 0:
            on_progress(out.states)
        if g.state.node_id:
            out.reached.add(g.state.node_id)
        if g.state.ended:
            if g.state.ending_node_id:
                out.endings.setdefault(g.state.ending_node_id, set()).add(g.state.ended)
            else:
                out.other_endings.add(g.state.ended)
            continue
        if out.states >= max_states:
            out.truncated = True
            break
        if g.state.combat is not None:
            moves = [a for a in g.available() if a.type in ("attack", "flee")]
        else:
            moves = [a for a in g.available() if a.type in _MOVES]
        for action in moves:
            for k in range(samples):
                salt += 1
                nxt = g.clone(seed=salt)
                events = _advance(nxt, action)
                sig = _signature(nxt, money_cap, watched)
                if sig not in seen:
                    seen.add(sig)
                    queue.append(nxt)
                if k == 0 and not any(e.type in _RANDOM for e in events):
                    break  # deterministic step: one sample is enough
    return out
