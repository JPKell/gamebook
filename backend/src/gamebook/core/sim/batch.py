"""Bot runs and batch statistics.

``play_run`` plays one game with a bot and returns a compact ``RunRecord``:
the chosen option indices (enough to replay the run exactly against the same
book) plus what aggregation needs. ``summarize`` turns many records into the
playtest dashboard's numbers.
"""

from __future__ import annotations

import random
import statistics
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from gamebook.core.engine.events import Action, Event
from gamebook.core.engine.game import Game, GameError
from gamebook.core.model import BookSnapshot
from gamebook.core.sim.bots import BotName, make_bot

#: Outcomes that count as the reader dying.
DEATHS = frozenset({"death", "defeated"})


@dataclass
class RunRecord:
    index: int
    seed: int
    #: The game's ending kind, or ``max_steps`` / ``error``.
    outcome: str
    ending_node_id: str | None
    last_node_id: str | None
    steps: int
    #: Index into ``Game.available()`` chosen at each step.
    picks: list[int]
    #: ``combat:<enemy key>``, ``node`` (an authored death), or ``stat`` (e.g. starvation).
    death_cause: str | None = None
    errors: int = 0
    error_sample: str | None = None
    # Aggregation only (not stored per run):
    visited: set[str] = field(default_factory=set)
    items_held: set[str] = field(default_factory=set)
    choices_taken: set[str] = field(default_factory=set)
    #: enemy key → [fights, fights lost]
    fights: dict[str, list[int]] = field(default_factory=dict)

    def stored(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "seed": self.seed,
            "outcome": self.outcome,
            "ending_node_id": self.ending_node_id,
            "last_node_id": self.last_node_id,
            "steps": self.steps,
            "picks": self.picks,
            "death_cause": self.death_cause,
            "errors": self.errors,
            "error_sample": self.error_sample,
        }


def bot_rng(bot: str, seed: int) -> random.Random:
    # String seeds hash with SHA-512, so this is stable across processes and runs.
    return random.Random(f"{bot}:{seed}")


class _Observer:
    """Folds a run's events into its record."""

    def __init__(self, rec: RunRecord) -> None:
        self.rec = rec
        self.foes: list[str] = []
        #: Enemy that last hurt the reader in the current fight.
        self.last_hitter: str | None = None
        #: The fight lost in the step being folded (deaths are blamed on it only then).
        self.lost_to: str | None = None

    def see(self, events: list[Event]) -> None:
        rec = self.rec
        for e in events:
            d = e.data
            match e.type:
                case "enter":
                    rec.visited.add(d["node"])
                case "effect" if d.get("op") == "give" and d.get("qty"):
                    rec.items_held.add(d["item"])
                case "item_taken" | "item_bought" if d.get("qty", 1):
                    rec.items_held.add(d["item"])
                case "action":
                    self.lost_to = None  # a new step: earlier lost fights didn't kill
                    if d["action"] == "choose":
                        rec.choices_taken.add(d["target"])
                case "combat_start":
                    self.foes = sorted({x["key"].partition("#")[0] for x in d["enemies"]})
                    self.last_hitter = None
                    for foe in self.foes:
                        rec.fights.setdefault(foe, [0, 0])[0] += 1
                case "combat_round" if d.get("hit") == "player":
                    self.last_hitter = d["enemy"].partition("#")[0]
                case "combat_end":
                    if d["outcome"] == "lose":
                        self.lost_to = self.last_hitter or (self.foes[0] if self.foes else None)
                        for foe in self.foes:
                            rec.fights[foe][1] += 1
                case "error":
                    rec.errors += 1
                    rec.error_sample = rec.error_sample or f"{d['where']}: {d['message']}"


class StopRun(Exception):  # noqa: N818 - control flow, not an error
    """Raised by a chooser to end a run early (e.g. a spending cap was reached)."""


#: Picks an index into ``options``. Gets the events of the previous step (or of
#: character creation) so a player can be told what just happened.
Chooser = Callable[[Game, list[Action], list[Event]], int]


def play_with(
    book: BookSnapshot,
    tier: str,
    seed: int,
    choose: Chooser,
    *,
    max_steps: int,
    index: int = 0,
) -> RunRecord:
    """Play one game with any chooser (a bot, or an LLM)."""
    rec = RunRecord(index, seed, "max_steps", None, None, 0, [])
    obs = _Observer(rec)
    stopped = False
    try:
        game = Game(book, tier, seed)
        last = game.start()
        obs.see(last)
        while not game.state.ended and game.state.steps < max_steps:
            options = game.available()
            if not options:
                break
            try:
                pick = choose(game, options, last)
            except StopRun:
                stopped = True
                break
            if not 0 <= pick < len(options):
                raise ValueError(f"Chooser picked {pick} of {len(options)} options")
            rec.picks.append(pick)
            last = game.step(options[pick])
            obs.see(last)
            game.log.clear()  # events are folded in; keep memory flat
    except Exception as exc:  # one broken run must not fail the batch
        rec.outcome = "error"
        rec.errors += 1
        rec.error_sample = rec.error_sample or f"{type(exc).__name__}: {exc}"
        return rec
    s = game.state
    rec.steps = s.steps
    rec.last_node_id = s.node_id
    if stopped:
        rec.outcome = "stopped"
    if s.ended:
        rec.outcome = s.ended
        rec.ending_node_id = s.ending_node_id
    if rec.outcome in DEATHS:
        if obs.lost_to:
            rec.death_cause = f"combat:{obs.lost_to}"
        elif s.ending_node_id:
            rec.death_cause = "node"
        else:
            rec.death_cause = "stat"
    return rec


def play_run(
    book: BookSnapshot, tier: str, seed: int, bot: BotName, *, max_steps: int, index: int = 0
) -> RunRecord:
    player = make_bot(bot)
    rng = bot_rng(bot, seed)
    return play_with(
        book,
        tier,
        seed,
        lambda game, options, _events: player.choose(game, options, rng),
        max_steps=max_steps,
        index=index,
    )


def replay_run(book: BookSnapshot, tier: str, seed: int, picks: list[int]) -> Game:
    """Rebuild a stored run (its full event log is ``game.log``)."""
    game = Game(book, tier, seed)
    game.start()
    for i, pick in enumerate(picks):
        options = game.available()
        if not 0 <= pick < len(options):
            raise GameError(f"Step {i + 1} no longer matches the book")
        game.step(options[pick])
    return game


def _pct(values: list[int], q: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


def summarize(book: BookSnapshot, records: list[RunRecord]) -> dict[str, Any]:
    """The playtest dashboard's numbers for one batch (JSON-friendly)."""
    n = len(records)
    wins = [r.outcome == "victory" for r in records]
    outcomes = Counter(r.outcome for r in records)
    endings = Counter(r.ending_node_id for r in records if r.ending_node_id)
    visits: Counter[str] = Counter()
    for r in records:
        visits.update(r.visited)
    deaths = Counter(r.last_node_id for r in records if r.outcome in DEATHS and r.last_node_id)
    causes = Counter(r.death_cause for r in records if r.death_cause)

    node_act = {nd.id: nd.act_id for nd in book.nodes}
    acts = []
    for act in sorted(book.acts, key=lambda a: a.position):
        reached = sum(1 for r in records if any(node_act.get(v) == act.id for v in r.visited))
        acts.append({"act_id": act.id, "title": act.title, "reached": reached})

    fights: dict[str, list[int]] = {}
    for r in records:
        for foe, (f, lost) in r.fights.items():
            agg = fights.setdefault(foe, [0, 0])
            agg[0] += f
            agg[1] += lost
    enemies = {
        k: {"fights": f, "losses": lost, "deaths": causes.get(f"combat:{k}", 0)}
        for k, (f, lost) in sorted(fights.items())
    }

    win_total = sum(wins)
    items: dict[str, dict[str, Any]] = {}
    for key in sorted({k for r in records for k in r.items_held}):
        held = [r.outcome == "victory" for r in records if key in r.items_held]
        without = n - len(held)
        lift = None
        if held and without:
            lift = round(sum(held) / len(held) - (win_total - sum(held)) / without, 4)
        items[key] = {"held_runs": len(held), "wins_with": sum(held), "lift": lift}

    ending_nodes = [nd.id for nd in book.nodes if nd.ending_kind]
    all_choices = [c.id for nd in book.nodes for c in nd.choices]
    taken = set().union(*(r.choices_taken for r in records)) if records else set()
    steps = [r.steps for r in records]
    errors = [r for r in records if r.errors]
    return {
        "runs": n,
        "win_rate": round(win_total / n, 4) if n else 0.0,
        "outcomes": dict(outcomes.most_common()),
        "endings": dict(endings.most_common()),
        "steps": {
            "mean": round(statistics.fmean(steps), 2) if steps else 0,
            "p50": _pct(steps, 0.5),
            "p90": _pct(steps, 0.9),
            "max": max(steps, default=0),
        },
        "node_visits": dict(sorted(visits.items())),
        "deaths_by_node": dict(deaths.most_common()),
        "death_causes": dict(causes.most_common()),
        "acts": acts,
        "enemies": enemies,
        "items": items,
        "coverage": {
            "nodes_total": len(book.nodes),
            "nodes_visited": len(visits),
            "unvisited": [nd.id for nd in book.nodes if nd.id not in visits],
            "endings_total": len(ending_nodes),
            "endings_reached": sum(1 for e in ending_nodes if e in endings),
            "choices_total": len(all_choices),
            "choices_taken": len(taken & set(all_choices)),
        },
        "errors": {
            "runs": len(errors),
            "sample": sorted({r.error_sample for r in errors if r.error_sample})[:5],
        },
    }
