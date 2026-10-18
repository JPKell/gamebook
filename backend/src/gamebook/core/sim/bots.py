"""Rule-based bot players.

A bot picks one of the currently available actions. Bots draw their own
randomness from a separate ``random.Random`` (never the game's dice), so a
run is fully described by ``(book, tier, seed, bot)`` and replays exactly
from the list of chosen indices.
"""

from __future__ import annotations

import random
from typing import Literal, Protocol

from gamebook.core.effects import ModifyStat
from gamebook.core.engine.events import Action
from gamebook.core.engine.game import Game

BotName = Literal["random", "greedy", "cautious", "explorer", "completionist"]
BOT_NAMES: tuple[BotName, ...] = ("random", "greedy", "cautious", "explorer", "completionist")

BOT_DESCRIPTIONS: dict[BotName, str] = {
    "random": "Picks any available action uniformly at random.",
    "greedy": "Takes and buys everything, equips into empty slots, otherwise chooses at random.",
    "cautious": "Prefers plain choices over rolls, tests and fights; heals when hurt; flees when low.",
    "explorer": "Heads for the least-visited places first.",
    "completionist": "Takes and buys everything and tries every choice it hasn't taken yet.",
}


class Bot(Protocol):
    def choose(self, game: Game, options: list[Action], rng: random.Random) -> int: ...


# ── shared heuristics ─────────────────────────────────────────────────────


def _health(game: Game) -> float | None:
    """Fraction of the damage stat left, when it has a maximum."""
    rules = game.combat_rules
    if rules is None:
        return None
    cap = game.state.max_stats.get(rules.damage_stat)
    if not cap:
        return None
    return game.state.stats.get(rules.damage_stat, 0) / cap


def _heals(game: Game, item_key: str) -> bool:
    rules = game.combat_rules
    item = game._items.get(item_key)
    if rules is None or item is None:
        return False
    return any(
        isinstance(e, ModifyStat)
        and e.stat == rules.damage_stat
        and not e.amount.strip().startswith("-")
        for e in item.use_effects
    )


def _index(options: list[Action], *types: str) -> list[int]:
    return [i for i, a in enumerate(options) if a.type in types]


def _equip_empty(game: Game, options: list[Action]) -> int | None:
    """Equip into an empty slot only (never swap, so bots can't flip-flop forever)."""
    for i, a in enumerate(options):
        if a.type != "equip":
            continue
        item = game._items.get(a.target or "")
        if item and item.slot and item.slot not in game.state.equipped:
            return i
    return None


def _heal(game: Game, options: list[Action], below: float) -> int | None:
    h = _health(game)
    if h is None or h >= below:
        return None
    for i in _index(options, "use"):
        if _heals(game, options[i].target or ""):
            return i
    return None


def _targets(game: Game, choice_id: str) -> list[str]:
    node = game.node
    if node is None:
        return []
    choice = next((c for c in node.choices if c.id == choice_id), None)
    if choice is None:
        return []
    return [o.target_id for o in choice.outcomes if o.target_id]


def _visits(game: Game, node_id: str) -> int:
    node = game._nodes.get(node_id)
    return game.state.visits.get(node.key, 0) if node else 0


def _fallback(options: list[Action], rng: random.Random) -> int:
    """Anything but selling or unequipping, unless that's all there is."""
    calm = [i for i, a in enumerate(options) if a.type not in ("sell", "unequip")]
    return rng.choice(calm) if calm else rng.randrange(len(options))


def _in_combat(game: Game, options: list[Action], rng: random.Random) -> int:
    attack = _index(options, "attack")
    return attack[0] if attack else _fallback(options, rng)


# ── bots ──────────────────────────────────────────────────────────────────


class RandomBot:
    def choose(self, game: Game, options: list[Action], rng: random.Random) -> int:
        return rng.randrange(len(options))


class GreedyBot:
    def choose(self, game: Game, options: list[Action], rng: random.Random) -> int:
        if game.state.combat is not None:
            return _in_combat(game, options, rng)
        for kind in ("take", "buy"):
            found = _index(options, kind)
            if found:
                return found[0]
        eq = _equip_empty(game, options)
        if eq is not None:
            return eq
        choices = _index(options, "choose")
        return rng.choice(choices) if choices else _fallback(options, rng)


class CautiousBot:
    def choose(self, game: Game, options: list[Action], rng: random.Random) -> int:
        if game.state.combat is not None:
            heal = _heal(game, options, 0.35)
            if heal is not None:
                return heal
            flee = _index(options, "flee")
            h = _health(game)
            if flee and h is not None and h < 0.3:
                return flee[0]
            return _in_combat(game, options, rng)
        heal = _heal(game, options, 0.5)
        if heal is not None:
            return heal
        take = _index(options, "take")
        if take:
            return take[0]
        eq = _equip_empty(game, options)
        if eq is not None:
            return eq
        choices = _index(options, "choose")
        if not choices:
            return _fallback(options, rng)
        node = game.node
        kinds = {c.id: c.kind for c in node.choices} if node else {}
        safe = [i for i in choices if kinds.get(options[i].target or "") == "goto"]
        return rng.choice(safe or choices)


class ExplorerBot:
    def choose(self, game: Game, options: list[Action], rng: random.Random) -> int:
        if game.state.combat is not None:
            return _in_combat(game, options, rng)
        take = _index(options, "take")
        if take:
            return take[0]
        eq = _equip_empty(game, options)
        if eq is not None:
            return eq
        choices = _index(options, "choose")
        if not choices:
            return _fallback(options, rng)
        return _least_visited(game, options, choices, rng)


def _least_visited(
    game: Game, options: list[Action], choices: list[int], rng: random.Random
) -> int:
    def score(i: int) -> int:
        targets = _targets(game, options[i].target or "")
        return min((_visits(game, t) for t in targets), default=0)

    best = min(score(i) for i in choices)
    return rng.choice([i for i in choices if score(i) == best])


class CompletionistBot:
    def __init__(self) -> None:
        self.taken: set[str] = set()

    def choose(self, game: Game, options: list[Action], rng: random.Random) -> int:
        if game.state.combat is not None:
            heal = _heal(game, options, 0.35)
            return heal if heal is not None else _in_combat(game, options, rng)
        heal = _heal(game, options, 0.5)
        if heal is not None:
            return heal
        for kind in ("take", "buy"):
            found = _index(options, kind)
            if found:
                return found[0]
        eq = _equip_empty(game, options)
        if eq is not None:
            return eq
        choices = _index(options, "choose")
        if not choices:
            return _fallback(options, rng)
        fresh = [i for i in choices if options[i].target not in self.taken]
        pick = _least_visited(game, options, fresh or choices, rng)
        self.taken.add(options[pick].target or "")
        return pick


def make_bot(name: BotName) -> Bot:
    bots: dict[BotName, type[Bot]] = {
        "random": RandomBot,
        "greedy": GreedyBot,
        "cautious": CautiousBot,
        "explorer": ExplorerBot,
        "completionist": CompletionistBot,
    }
    return bots[name]()
