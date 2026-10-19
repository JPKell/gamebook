"""Prove a compiled print edition plays like the engine.

Bots play the book in the engine. At every move the verifier asks the printed book
the same question a reader would: from the section I'm reading, does the instruction
for this choice (and this outcome: success, a roll band, a won fight...) send me to
the section the engine went to? On arrival, does the router send me to the text
variant the engine chose? Endings must be printed where the engine ends. A printed
book that passes has every transition the bots took, numbered correctly.

Structural checks run too: numbers are 1..N with no gaps or repeats, and every
"turn to" points at a section that exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gamebook.core.engine.events import Event
from gamebook.core.engine.game import Game
from gamebook.core.model import BookSnapshot
from gamebook.core.printbook.compile import PrintBook, Section
from gamebook.core.sim.batch import bot_rng
from gamebook.core.sim.bots import BOT_NAMES, make_bot

MAX_SAMPLES = 25


@dataclass
class VerifyReport:
    runs: int = 0
    moves: int = 0
    arrivals: int = 0
    problems: int = 0
    samples: list[str] = field(default_factory=list)
    #: Printed sections no run reached (not an error: bots may just not find them).
    unvisited: list[int] = field(default_factory=list)
    structure: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.problems == 0 and not self.structure

    def flag(self, message: str) -> None:
        self.problems += 1
        if len(self.samples) < MAX_SAMPLES and message not in self.samples:
            self.samples.append(message)


def structure(printed: PrintBook) -> list[str]:
    out = []
    numbers = sorted(s.number for s in printed.sections)
    if numbers != list(range(1, len(numbers) + 1)):
        out.append("Section numbers aren't 1..N without gaps or repeats")
    have = set(numbers)
    for s in printed.sections:
        for link in s.links:
            if link.number is not None and link.number not in have:
                out.append(f"Section {s.number} turns to {link.number}, which doesn't exist")
        for r in s.routes:
            if r.number not in have:
                out.append(f"Section {s.number} routes to {r.number}, which doesn't exist")
    return out[:MAX_SAMPLES]


def static(book: BookSnapshot, printed: PrintBook) -> list[str]:
    """Section-by-section checks against the engine's own rules (no dice needed):
    routers list the variants the engine tries, in its order; each section prints
    exactly the choices and effects the engine applies in this edition; the start is
    where "turn to" sends the reader."""
    out: list[str] = []
    game = Game(book, printed.tier, 1)
    nodes = {n.id: n for n in book.nodes}
    start = printed.numbers.get(f"n:{book.start_node_id}") if book.start_node_id else None
    if start is not None and printed.start != start:
        out.append(f"The book says to start at {printed.start}, but the start is section {start}")
    for s in printed.sections:
        n = nodes.get(s.node_id)
        if n is None:
            out.append(f"Section {s.number} prints a node that doesn't exist")
            continue
        if s.kind == "router":
            want: list[str | None] = []
            for v in sorted(n.variants, key=lambda v: -v.priority):
                want.append(v.condition)
                if not v.condition:
                    break
            if all(want):
                want.append(None)  # the plain fallback
            if [r.condition for r in s.routes] != want:
                out.append(f"Section {s.number} routes in a different order than the engine")
            continue
        choices = [b for b in s.blocks if b.kind == "choice"]
        if n.ending_kind is None:
            offered = {c.id for c in n.choices if game.tier_allows(c.min_tier)}
            printed_ids = {b.data["choice_id"] for b in choices}
            if printed_ids != offered:
                out.append(f"Section {s.number} prints different choices than the engine offers")
        allowed = sum(game.tier_allows(e.min_tier) for e in n.on_enter)
        lines = sum(len(b.data["lines"]) for b in s.blocks if b.kind == "effects")
        if lines != allowed:
            out.append(f"Section {s.number} prints {lines} effect(s); the engine applies {allowed}")
        by_id = {c.id: c for c in n.choices}
        for b in choices:
            ch = by_id.get(b.data["choice_id"])
            if ch is None:
                continue
            want_n = sum(game.tier_allows(e.min_tier) for e in ch.effects)
            got = len(b.data["effects"]) + len(b.data["first_effects"])
            if got != want_n:
                out.append(
                    f"Section {s.number}: '{ch.label}' prints {got} effect(s); the engine applies {want_n}"
                )
        if (n.ending_kind is not None) != (s.ending is not None):
            out.append(f"Section {s.number}'s ending doesn't match the engine")
    return out[:MAX_SAMPLES]


class _Reader:
    """Follows the engine through the printed book."""

    def __init__(self, printed: PrintBook, report: VerifyReport) -> None:
        self.by_number = printed.by_number()
        self.numbers = printed.numbers
        self.report = report
        self.here: Section | None = None
        self.visited: set[int] = set()

    def section(self, number: int | None) -> Section | None:
        return self.by_number.get(number) if number is not None else None

    def arrive(self, entry: Section | None, event: Event) -> None:
        """At a node's entry section; follow its router to the variant the engine chose."""
        r = self.report
        r.arrivals += 1
        node, variant = event.data["node"], event.data.get("variant")
        if entry is None or entry.node_id != node:
            r.flag(f"Arrived at a section that isn't the engine's node {node}")
            self.here = None
            return
        self.visited.add(entry.number)
        if entry.kind != "router":
            self.here = entry
            return
        route = next((x for x in entry.routes if x.variant_id == variant), None)
        if route is None:
            r.flag(f"Section {entry.number} has no route for the text the engine chose")
            self.here = None
            return
        self.here = self.section(route.number)
        if self.here is not None:
            self.visited.add(self.here.number)

    def outcome(self, choice_id: str, outcome: str, next_entry: Event | None) -> None:
        r = self.report
        r.moves += 1
        here = self.here
        if here is None:
            return
        link = next(
            (x for x in here.links if x.choice_id == choice_id and x.outcome == outcome), None
        )
        if link is None:
            r.flag(
                f"Section {here.number} has no instruction for a move the engine made ({outcome})"
            )
            self.here = None
            return
        if next_entry is None:
            return
        want = self.numbers.get(f"n:{next_entry.data['node']}")
        if link.number != want:
            r.flag(f"Section {here.number} turns to {link.number} where the engine went to {want}")
        self.arrive(self.section(link.number), next_entry)


def verify(
    book: BookSnapshot,
    printed: PrintBook,
    *,
    runs: int = 200,
    seed: int = 1,
    max_steps: int = 400,
) -> VerifyReport:
    report = VerifyReport(structure=structure(printed) + static(book, printed))
    reader_visited: set[int] = set()
    for i in range(runs):
        bot_name = BOT_NAMES[i % len(BOT_NAMES)]
        bot, rng = make_bot(bot_name), bot_rng(bot_name, seed + i)
        game = Game(book, printed.tier, seed + i)
        events = game.start()
        reader = _Reader(printed, report)
        enter = next((e for e in events if e.type == "enter"), None)
        if enter is not None:
            reader.arrive(reader.section(printed.numbers.get(f"n:{enter.data['node']}")), enter)
        report.runs += 1
        while not game.state.ended and game.state.steps < max_steps:
            options = game.available()
            if not options:
                break
            events = game.step(options[bot.choose(game, options, rng)])
            game.log.clear()
            outcomes = [k for k, e in enumerate(events) if e.type == "outcome"]
            for k in outcomes:
                after = next((e for e in events[k + 1 :] if e.type == "enter"), None)
                reader.outcome(events[k].data["choice"], events[k].data["outcome"], after)
        s = game.state
        here = reader.here
        authored = s.ending_node_id is not None  # an authored ending node, any kind
        if authored and here and here.ending is None:
            report.flag(f"The engine's game ended at section {here.number}, which prints no ending")
        reader_visited |= reader.visited
    report.unvisited = sorted(set(printed.by_number()) - reader_visited)
    return report
