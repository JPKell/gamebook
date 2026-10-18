from dataclasses import replace
from typing import Any

from gamebook.core.analysis import Problem, validate_book
from gamebook.core.model import (
    BookSnapshot,
    Choice,
    Encounter,
    EncounterEnemy,
    Enemy,
    Node,
    Outcome,
    RandomTable,
    TableEntry,
    Variant,
)

from .builders import book, effects, ending, goto, node, with_choices


def codes(problems: list[Problem]) -> list[str]:
    return [p.code for p in problems]


def simple_book(**kw: Any) -> BookSnapshot:
    return book(
        with_choices(node("start"), goto("start", "end")),
        ending("end"),
        **kw,
    )


def test_minimal_book_is_clean() -> None:
    assert validate_book(simple_book()) == []


def test_empty_book_is_clean() -> None:
    assert validate_book(book(start=None)) == []


def test_no_start() -> None:
    b = book(with_choices(node("a"), goto("a", "end")), ending("end"), start=None)
    assert "no_start" in codes(validate_book(b))


def test_dead_end_and_ending_with_choices() -> None:
    b = book(
        with_choices(node("start"), goto("start", "stuck"), goto("start", "end")),
        node("stuck"),
        with_choices(ending("end"), goto("end", "start")),
    )
    c = codes(validate_book(b))
    assert "dead_end" in c
    assert "ending_has_choices" in c


def test_unreachable_and_no_ending() -> None:
    b = book(
        with_choices(node("start"), goto("start", "end"), goto("start", "loop")),
        with_choices(node("loop"), goto("loop", "loop")),
        ending("end"),
        with_choices(node("island"), goto("island", "end")),
    )
    problems = validate_book(b)
    assert {(p.code, p.node_id) for p in problems} >= {
        ("unreachable", "island"),
        ("no_ending", "loop"),
    }


def test_outcome_targets() -> None:
    b = book(
        with_choices(
            node("start"),
            goto("start", None, "Nowhere"),
            goto("start", "ghost"),
            goto("start", "end"),
        ),
        ending("end"),
    )
    c = codes(validate_book(b))
    assert "outcome_no_target" in c
    assert "outcome_bad_target" in c


# ── acts ────────────────────────────────────────────────────────────────


def three_acts(**overrides: Node) -> BookSnapshot:
    nodes = {
        "start": with_choices(node("start", "act1", is_act_exit=True), goto("start", "a2")),
        "a2": with_choices(
            node("a2", "act2", is_act_entry=True, is_act_exit=True), goto("a2", "a3")
        ),
        "a3": with_choices(node("a3", "act3", is_act_entry=True), goto("a3", "end")),
        "end": ending("end", "act3"),
    }
    nodes.update(overrides)
    return book(*nodes.values(), acts=3)


def test_three_act_book_is_clean() -> None:
    assert validate_book(three_acts()) == []


def test_act_needs_exit_and_entry() -> None:
    b = three_acts(
        start=with_choices(node("start", "act1"), goto("start", "a2")),
        a2=with_choices(node("a2", "act2", is_act_exit=True), goto("a2", "a3")),
    )
    c = codes(validate_book(b))
    assert "act_no_exit" in c
    assert "act_no_entry" in c
    assert "act_boundary" in c


def test_act_skip_and_backwards() -> None:
    b = three_acts(
        start=with_choices(
            node("start", "act1", is_act_exit=True), goto("start", "a2"), goto("start", "a3")
        ),
        a3=with_choices(node("a3", "act3", is_act_entry=True), goto("a3", "end"), goto("a3", "a2")),
    )
    c = codes(validate_book(b))
    assert "act_skip" in c
    assert "act_backwards" in c


def test_exit_without_link_and_entry_without_incoming() -> None:
    b = three_acts(
        start=with_choices(node("start", "act1", is_act_exit=True), goto("start", "s2")),
        s2=with_choices(node("s2", "act1", is_act_exit=True), goto("s2", "a2")),
    )
    assert ("exit_unlinked", "start") in {(p.code, p.node_id) for p in validate_book(b)}


# ── choices ─────────────────────────────────────────────────────────────


def roll_choice(ranges: list[tuple[int | None, int | None]], dice: str = "2d6") -> Choice:
    return Choice(
        id="roll",
        node_id="start",
        label="Roll",
        kind="roll",
        dice=dice,
        outcomes=tuple(
            Outcome(id=f"o{i}", key=f"r{i}", target_id="end", range_lo=lo, range_hi=hi)
            for i, (lo, hi) in enumerate(ranges)
        ),
    )


def test_roll_coverage() -> None:
    ok = book(with_choices(node("start"), roll_choice([(2, 6), (7, 12)])), ending("end"))
    assert validate_book(ok) == []

    bad = book(with_choices(node("start"), roll_choice([(2, 5), (7, 13), (12, 12)])), ending("end"))
    problems = {p.code: p.message for p in validate_book(bad)}
    assert "no outcome for rolls of 6" in problems["roll_gap"]
    assert "rolls of 12" in problems["roll_overlap"]

    unbounded = book(
        with_choices(node("start"), roll_choice([(1, 30)], "2d6 + SKILL")), ending("end")
    )
    assert codes(validate_book(unbounded)) == ["roll_unbounded"]

    missing = book(with_choices(node("start"), roll_choice([(None, None)])), ending("end"))
    assert "roll_range" in codes(validate_book(missing))


def test_test_choice() -> None:
    def test_choice(test: str | None, keys: tuple[str, ...], min_tier: str | None = None) -> Choice:
        return Choice(
            id="t",
            node_id="start",
            label="Test",
            kind="test",
            test=test,
            min_tier=min_tier,
            outcomes=tuple(Outcome(id=k, key=k, target_id="end") for k in keys),
        )

    ok = book(
        with_choices(node("start"), test_choice("luck", ("success", "failure"))), ending("end")
    )
    assert validate_book(ok) == []
    c = codes(
        validate_book(
            book(with_choices(node("start"), test_choice("nope", ("success",))), ending("end"))
        )
    )
    assert "unknown_test" in c
    assert "outcomes" in c


def test_combat_choice() -> None:
    enc = Encounter(id="enc", label="Orcs", enemies=(EncounterEnemy("e-orc", level=2, count=2),))
    fight = Choice(
        id="f",
        node_id="start",
        label="Fight",
        kind="combat",
        encounter_id="enc",
        outcomes=(Outcome("w", "win", "end"), Outcome("l", "lose", "dead")),
    )
    ok = book(
        replace(with_choices(node("start"), fight), encounters=(enc,)),
        ending("end"),
        ending("dead", kind="death"),
    )
    assert validate_book(ok) == []

    no_enc = book(
        with_choices(node("start"), replace(fight, flee_allowed=True)),
        ending("end"),
        ending("dead"),
    )
    c = codes(validate_book(no_enc))
    assert "combat_no_encounter" in c
    assert "outcomes" in c  # flee allowed but no flee outcome


def test_conditions_and_tier_scope() -> None:
    def gated(cond: str, min_tier: str | None = None) -> BookSnapshot:
        return book(
            with_choices(
                node("start"),
                replace(goto("start", "end", condition=cond, min_tier=min_tier), id="gated"),
                goto("start", "end", "Other"),
            ),
            ending("end"),
        )

    # Nobody can have rope here, which the state digest points out.
    assert codes(validate_book(gated("has(rope) and GOLD >= 5"))) == ["gate_never"]
    c = codes(validate_book(gated("has(sword)")))
    assert c == ["gbx.ref", "gate_never"]
    # ARMOR only exists from Medium: warning suggesting a min tier...
    assert codes(validate_book(gated("ARMOR > 2"))) == ["tier_scope"]
    # ...which goes away once the min tier is set.
    assert validate_book(gated("ARMOR > 2", "medium")) == []
    assert "unknown_tier" in codes(validate_book(gated("true", "legendary")))


def test_effects() -> None:
    n = replace(
        with_choices(node("start"), goto("start", "end")),
        on_enter=effects(
            {"op": "modify", "stat": "STAMINA", "amount": "-2"},
            {"op": "give", "item": "sword"},
            {"op": "modify", "stat": "MANA", "amount": "1"},
            {"op": "modify", "stat": "ARMOR", "amount": "1"},
            {"op": "learn", "skill": "TRACKING"},
            {"op": "modify", "stat": "GOLD", "amount": "1d6 +"},
        ),
    )
    found = {(p.code, p.field) for p in validate_book(book(n, ending("end")))}
    assert ("unknown_item", "on_enter[1]") in found
    assert ("unknown_stat", "on_enter[2]") in found
    assert ("tier_scope", "on_enter[3]") in found
    assert ("unknown_skill", "on_enter[4]") in found
    assert ("gbx.syntax", "on_enter[5]") in found


def test_flags_never_set() -> None:
    gate = replace(goto("start", "end", condition="flag(RAVEN)"), id="gate")
    b = book(with_choices(node("start"), gate, goto("start", "end", "Other")), ending("end"))
    assert codes(validate_book(b)) == ["flag_never_set", "gate_never"]

    # Set later in the book (after the gate): not "never set", though still never true here.
    setter = replace(ending("end"), on_enter=effects({"op": "set_flag", "flag": "RAVEN"}))
    assert codes(
        validate_book(
            book(with_choices(node("start"), gate, goto("start", "end", "Other")), setter)
        )
    ) == ["gate_never"]
    # Set in another book of the series: a reader may bring it along (no contradiction).
    assert codes(validate_book(replace(b, series_flags_set=frozenset({"RAVEN"})))) == []


def test_variants() -> None:
    no_default = replace(
        with_choices(node("start"), goto("start", "end")),
        variants=(Variant("v", "Return", "visits(start) > 1"),),
    )
    c = codes(validate_book(book(no_default, ending("end"))))
    assert "no_default_variant" in c
    assert "gbx.unprintable" in c
    two = replace(
        with_choices(node("start"), goto("start", "end")),
        variants=(Variant("a", "A"), Variant("b", "B")),
    )
    assert "shadowed_variant" in codes(validate_book(book(two, ending("end"))))


def test_enemies() -> None:
    weak = Enemy(id="e-rat", key="rat", name="Rat", stat_formulas={"SKILL": "4", "MANA": "1d6"})
    found = {(p.code, p.field) for p in validate_book(simple_book(enemies=(weak,)))}
    assert ("enemy_missing_stat", "stat_formulas.STAMINA") in found
    assert ("enemy_missing_stat", "stat_formulas.ARMOR") in found
    assert ("enemy_unused_stat", "stat_formulas.MANA") in found
    assert ("gbx.dice", "stat_formulas.MANA") in found


def test_book_scoped_entities() -> None:
    other = Enemy(id="e-x", key="x", name="X", book_id="other-book", stat_formulas={})
    # Entities from other books are ignored (not validated, not usable).
    assert validate_book(simple_book(enemies=(other,))) == []
    enc = Encounter(id="enc", label="X", enemies=(EncounterEnemy("e-x"),))
    b = book(
        replace(with_choices(node("start"), goto("start", "end")), encounters=(enc,)),
        ending("end"),
        enemies=(other,),
    )
    assert "unknown_enemy" in codes(validate_book(b))


def test_tables() -> None:
    table = RandomTable(
        id="t",
        key="t",
        name="Wandering",
        dice="1d6",
        entries=(
            TableEntry(1, 3, "enemies", enemies=(("orc", 1, 1),)),
            TableEntry(5, 6, "item", item="potion"),
        ),
    )
    found = codes(validate_book(simple_book(tables=(table,))))
    assert "table_gap" in found


def test_section_pins() -> None:
    b = book(
        with_choices(node("start", section_pin=1), goto("start", "end")),
        replace(ending("end"), section_pin=1),
    )
    assert codes(validate_book(b)).count("duplicate_pin") == 2


def test_problems_sorted_by_severity() -> None:
    b = book(with_choices(node("start"), goto("start", None)), node("stuck"))
    sev = [p.severity for p in validate_book(b)]
    assert sev == sorted(sev, key=["error", "warning", "info"].index)


def test_digest_rules() -> None:
    """Never/always-satisfiable gates, readers trapped behind them, bad canonical overrides."""
    b = book(
        with_choices(
            replace(node("start"), on_enter=effects({"op": "set_flag", "flag": "RAVEN"})),
            replace(goto("start", "hall", condition="flag(RAVEN)"), id="always"),
        ),
        with_choices(node("hall"), replace(goto("hall", "end", condition="has(rope)"), id="never")),
        replace(ending("end"), canonical_predecessor_id="start"),
    )
    found = {(p.code, p.choice_id or p.node_id) for p in validate_book(b)}
    assert ("gate_always", "always") in found
    assert ("gate_never", "never") in found
    assert ("trapped", "start") in found  # reported where readers first get stuck
    assert ("bad_canonical", "end") in found


def test_unreachable_through_impossible_choices_and_trapped_once() -> None:
    b = book(
        with_choices(
            node("start"),
            replace(goto("start", "vault", condition="has(rope)"), id="locked"),
            goto("start", "a"),
        ),
        with_choices(node("a"), goto("a", "b")),
        with_choices(node("b"), replace(goto("b", "end", condition="has(rope)"), id="b_gate")),
        with_choices(node("vault"), goto("vault", "end")),
        ending("end"),
    )
    found = [(p.code, p.node_id) for p in validate_book(b)]
    assert ("unreachable_gated", "vault") in found
    # start, a and b are all stuck; only the first stuck node is reported.
    assert [n for c, n in found if c == "trapped"] == ["start"]
