"""Write the TypeScript engine's parity corpus (run: ``uv run python -m tests.core.parity_corpus``).

Bots play the engine test book (and an "edge" variant with broken expressions, so
content-error events are pinned too) at every tier over many seeds. Each case keeps
the actions, the final state and a SHA-256 of the canonical event JSON; the TS
engine must replay every case to the same digest (frontend/src/engine/parity.test.ts).
Regenerate deliberately when the engine changes, like the golden traces.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from gamebook.core.engine.bundle import to_bundle
from gamebook.core.engine.game import Game
from gamebook.core.model import BookSnapshot
from gamebook.core.rules.schema import effective_tier
from gamebook.core.sim.batch import bot_rng
from gamebook.core.sim.bots import BOT_NAMES, make_bot

from .builders import effects
from .engine_book import engine_book

OUT = Path(__file__).parents[3] / "frontend/src/engine/__fixtures__/parity.json"
SEEDS = range(1, 9)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(events: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical(events).encode()).hexdigest()


def edge_book() -> BookSnapshot:
    """The test book plus content errors: unknown names, division by zero, bad syntax."""
    b = engine_book()
    nodes = []
    for n in b.nodes:
        if n.key == "trap":
            n = replace(
                n,
                on_enter=(
                    *n.on_enter,
                    *effects(
                        {"op": "modify", "stat": "GOLD", "amount": "nonsense + 1"},
                        {"op": "modify", "stat": "GOLD", "amount": "4 / (2 - 2)"},
                        {"op": "modify", "stat": "GOLD", "amount": "7 % -3 + 10 / 4"},
                        {"op": "set", "stat": "LUCK", "value": "max(LUCK, 3) - (true ? 1 : 2)"},
                        {"op": "modify", "stat": "GOLD", "amount": "2 +"},
                        # Exact big integers, and results too large for either engine.
                        {
                            "op": "modify",
                            "stat": "GOLD",
                            "amount": "123456789012345678901234567890 - 123456789012345678901234567889",
                        },
                        {"op": "modify", "stat": "GOLD", "amount": "9007199254740993 * 2"},
                    ),
                ),
            )
        if n.key == "start" and n.choices:
            first = n.choices[0]
            n = replace(
                n, choices=(replace(first, condition="has(rope) and GOLD >"), *n.choices[1:])
            )
        nodes.append(n)
    return replace(b, nodes=tuple(nodes))


def case(
    book: BookSnapshot, tier: str, seed: int, bot_name: str, creation: dict[str, Any]
) -> dict[str, Any]:
    bot, rng = make_bot(bot_name), bot_rng(bot_name, seed)  # type: ignore[arg-type]
    game = Game(book, tier, seed)
    game.start(**creation)
    actions: list[dict[str, Any]] = []
    while not game.state.ended and len(actions) < 150:
        options = game.available()
        if not options:
            break
        action = options[bot.choose(game, options, rng)]
        actions.append(action.to_dict())
        game.step(action)
    events = [e.to_dict() for e in game.log]
    return {
        "tier": tier,
        "seed": seed,
        "bot": bot_name,
        "creation": creation,
        "actions": actions,
        "events": len(events),
        "digest": digest(events),
        "final_state": game.state.to_dict(),
    }


def build() -> dict[str, Any]:
    books = {"engine": engine_book(), "edge": edge_book()}
    out: dict[str, Any] = {"books": {k: to_bundle(b) for k, b in books.items()}, "cases": {}}
    for name, book in books.items():
        assert book.rules is not None
        cases = []
        for tier in book.rules.tier_keys():
            classes = list(effective_tier(book.rules, tier).classes)
            for seed in SEEDS:
                bot_name = BOT_NAMES[seed % len(BOT_NAMES)]
                creation = {"character_class": classes[seed % len(classes)]} if classes else {}
                cases.append(case(book, tier, seed, bot_name, creation))
        out["cases"][name] = cases
    return out


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=None, sort_keys=True) + "\n")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
