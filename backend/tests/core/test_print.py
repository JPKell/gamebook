"""Section numbering, the print compiler and the printed-book verifier."""

from __future__ import annotations

from dataclasses import replace

import pytest

from gamebook.core.printbook import compile as pc
from gamebook.core.printbook import numbering
from gamebook.core.printbook.verify import verify

from .builders import effects
from .engine_book import engine_book


def test_numbers_are_per_act_ranges_pinned_and_stable() -> None:
    acts = [["a", "b", "c"], ["d", "e"]]
    first = numbering.assign(acts, seed=3, pins={"b": 1}, previous={})
    assert first.numbers["b"] == 1
    assert sorted(first.numbers[k] for k in ("a", "b", "c")) == [1, 2, 3]
    assert sorted(first.numbers[k] for k in ("d", "e")) == [4, 5]
    # Same seed and history: same numbers. A new key keeps the others.
    again = numbering.assign(
        [["a", "b", "c", "z"], ["d", "e"]], seed=3, pins={"b": 1}, previous=first.numbers
    )
    assert {k: again.numbers[k] for k in ("a", "b", "c")} == {
        k: first.numbers[k] for k in ("a", "b", "c")
    }
    assert again.numbers["z"] == 4
    # A pin outside its act's range is reported, not applied.
    bad = numbering.assign(acts, seed=3, pins={"d": 1}, previous={})
    assert bad.ignored_pins == {"d": 1}
    assert bad.numbers["d"] in (4, 5)


def test_different_seeds_shuffle() -> None:
    keys = [[f"k{i}" for i in range(40)]]
    a = numbering.assign(keys, seed=1, pins={}, previous={}).numbers
    b = numbering.assign(keys, seed=2, pins={}, previous={}).numbers
    assert a != b
    assert sorted(a.values()) == list(range(1, 41))


def _compiled(tier: str = "advanced") -> tuple[pc.PrintBook, object]:
    book = engine_book()
    nums = numbering.assign(pc.section_keys(book), seed=7, pins=pc.pins(book), previous={})
    return pc.compile_book(book, tier, nums.numbers, prose={}, notes={}), book


def test_compiler_routes_variants_and_ticks_visits() -> None:
    printed, _ = _compiled()
    start = next(s for s in printed.sections if s.number == 1)
    assert start.kind == "router"  # two text variants, chosen by visits(start)
    assert start.ticks == 2  # "more than once" needs two boxes
    lines = [line["text"] for line in start.blocks[0].data["lines"]]
    assert lines[0].startswith("If you have been to section 1 more than once")
    assert lines[-1] == "Otherwise, turn to"
    # Each variant section repeats the mechanics; once-only gains are first-visit only.
    variants = [s for s in printed.sections if s.node_id == start.node_id and s.kind == "section"]
    assert len(variants) == 2
    effects = next(b for b in variants[0].blocks if b.kind == "effects")
    assert effects.data["lead"] == (
        "If this is your first visit (the first box at section 1 was empty when you arrived):"
    )


def test_compiler_phrases_mechanics_per_edition() -> None:
    advanced, _ = _compiled("advanced")
    basic, _ = _compiled("basic")

    def choices(printed: pc.PrintBook) -> list[str]:
        return [b.data["label"] for s in printed.sections for b in s.blocks if b.kind == "choice"]

    assert "Elite path" in choices(advanced)
    assert "Elite path" not in choices(basic)  # tier-limited choices leave lower editions
    hall = next(s for s in advanced.sections if s.title == "Hall")
    kinds = {b.data["kind"]: b.data for b in hall.blocks if b.kind == "choice"}
    assert [o["text"] for o in kinds["roll"]["outcomes"]] == [
        "2\u20136: turn to",
        "7\u201312: turn to",
    ]
    assert kinds["test"]["test"]["label"] == "Test your Luck"
    assert kinds["combat"]["fight"]["labels"][:2] == ["Skill", "Stamina"]
    assert any("flee" in o["text"] for o in kinds["combat"]["outcomes"])
    market = next(s for s in advanced.sections if s.title == "Market")
    shop = next(b for b in market.blocks if b.kind == "shop")
    assert shop.data["rows"][0] == {"name": "Sword", "price": 8, "stock": 1}


@pytest.mark.parametrize("tier", ["basic", "medium", "advanced"])
def test_verifier_passes_a_correct_book(tier: str) -> None:
    printed, book = _compiled(tier)
    report = verify(book, printed, runs=80)  # type: ignore[arg-type]
    assert report.ok, report.samples
    assert report.moves > 80


def test_verifier_catches_a_wrong_number() -> None:
    printed, book = _compiled()
    hall = next(s for s in printed.sections if s.title == "Hall")
    hall.links[0].number = 2 if hall.links[0].number != 2 else 3
    report = verify(book, printed, runs=80)  # type: ignore[arg-type]
    assert not report.ok
    assert any("turns to" in s for s in report.samples)


def test_verifier_catches_gaps_and_dangling_links() -> None:
    printed, book = _compiled()
    printed.sections[-1].number += 10
    report = verify(book, printed, runs=5)  # type: ignore[arg-type]
    assert report.structure


# ── review regressions ────────────────────────────────────────────────────


def _with_node(book: object, node_id: str, **changes: object) -> object:
    b = book  # BookSnapshot
    nodes = tuple(replace(n, **changes) if n.id == node_id else n for n in b.nodes)  # type: ignore[attr-defined]
    return replace(b, nodes=nodes)  # type: ignore[type-var]


def _compile(book: object, tier: str) -> pc.PrintBook:
    nums = numbering.assign(pc.section_keys(book), seed=7, pins=pc.pins(book), previous={})  # type: ignore[arg-type]
    return pc.compile_book(book, tier, nums.numbers, prose={}, notes={})  # type: ignore[arg-type]


def _lines(printed: pc.PrintBook, title: str) -> list[str]:
    return [
        line
        for s in printed.sections
        if s.title == title
        for b in s.blocks
        if b.kind == "effects"
        for line in b.data["lines"]
    ]


def test_tier_limited_effects_stay_out_of_lower_editions() -> None:
    base = engine_book()
    trap = next(n for n in base.nodes if n.title == "Trap")
    book = _with_node(
        base,
        trap.id,
        on_enter=(
            *trap.on_enter,
            *effects({"op": "modify", "stat": "GOLD", "amount": "100", "min_tier": "advanced"}),
        ),
    )
    basic, advanced = _compile(book, "basic"), _compile(book, "advanced")
    assert not any("100" in line for line in _lines(basic, "Trap"))
    assert any("100" in line for line in _lines(advanced, "Trap"))
    assert verify(book, basic, runs=20).ok  # type: ignore[arg-type]


def test_once_only_and_repeating_choice_effects_are_split() -> None:
    base = engine_book()
    start = next(n for n in base.nodes if n.id == "start")
    first = start.choices[0]
    changed = replace(
        first,
        effects=effects(
            {"op": "modify", "stat": "STAMINA", "amount": "-2"}, {"op": "give", "item": "rope"}
        ),
    )
    book = _with_node(base, "start", choices=(changed, *start.choices[1:]))
    printed = _compile(book, "advanced")
    block = next(
        b
        for s in printed.sections
        if s.node_id == "start"
        for b in s.blocks
        if b.kind == "choice" and b.data["choice_id"] == first.id
    )
    assert block.data["effects"] == ["Deduct 2 from your Stamina."]
    assert block.data["first_effects"] == ["You gain the Rope."]
    assert verify(book, printed, runs=20).ok  # type: ignore[arg-type]


def test_unreachable_variants_leave_no_gaps() -> None:
    base = engine_book()
    start = next(n for n in base.nodes if n.id == "start")
    default, back = start.variants
    # The unconditional variant now outranks the conditional one: "back" is unreachable.
    book = _with_node(base, "start", variants=(replace(default, priority=5), back))
    printed = _compile(book, "advanced")
    assert sorted(s.number for s in printed.sections) == list(range(1, len(printed.sections) + 1))
    assert verify(book, printed, runs=20).ok  # type: ignore[arg-type]


def test_start_pinned_elsewhere_is_where_the_book_begins() -> None:
    base = engine_book()
    book = _with_node(base, "hall", section_pin=1)
    printed = _compile(book, "advanced")
    start = printed.numbers["n:start"]
    assert start != 1
    assert printed.start == start
    assert any(w.code == "start_not_one" for w in printed.warnings)
    report = verify(book, printed, runs=10)  # type: ignore[arg-type]
    assert report.ok, report.structure
    printed.start = 1  # what the old template assumed
    assert any("start at" in s for s in verify(book, printed, runs=1).structure)  # type: ignore[arg-type]


def test_verifier_checks_printed_effects_choices_and_routes() -> None:
    printed, book = _compiled()
    trap = next(s for s in printed.sections if s.title == "Trap")
    next(b for b in trap.blocks if b.kind == "effects").data["lines"].append(
        "Add 100 to your Gold."
    )
    hall = next(s for s in printed.sections if s.title == "Hall")
    hall.blocks = [b for b in hall.blocks if not (b.kind == "choice" and b.data["kind"] == "roll")]
    router = next(s for s in printed.sections if s.kind == "router")
    router.routes.reverse()
    problems = verify(book, printed, runs=1).structure  # type: ignore[arg-type]
    assert any("effect(s)" in p for p in problems)
    assert any("different choices" in p for p in problems)
    assert any("routes in a different order" in p for p in problems)


def test_unknown_tier_choices_are_hidden_like_the_engine() -> None:
    base = engine_book()
    start = next(n for n in base.nodes if n.id == "start")
    odd = replace(start.choices[0], min_tier="legendary")
    book = _with_node(base, "start", choices=(odd, *start.choices[1:]))
    printed = _compile(book, "advanced")
    ids = {b.data["choice_id"] for s in printed.sections for b in s.blocks if b.kind == "choice"}
    assert odd.id not in ids
    assert verify(book, printed, runs=10).ok  # type: ignore[arg-type]
