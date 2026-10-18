"""State digest: must/may facts, gates, depths and canonical predecessors."""

from __future__ import annotations

from dataclasses import replace

from gamebook.core.analysis.digest import compute
from gamebook.core.model import Entity, Item, Node

from .builders import book, effects, ending, goto, node, with_choices

ITEMS = (
    Item(id="i-rope", key="rope", name="Rope"),
    Item(id="i-key", key="silver_key", name="Silver Key", category="key"),
    Item(
        id="i-potion",
        key="potion",
        name="Potion",
        category="consumable",
        use_effects=effects({"op": "set_flag", "flag": "DRANK"}),
    ),
)


def diamond() -> list[Node]:
    """start → left (rope) | right → join → end; start sets RAVEN."""
    return [
        replace(
            with_choices(node("start"), goto("start", "left", "Left"), goto("start", "right")),
            on_enter=effects({"op": "set_flag", "flag": "RAVEN"}),
        ),
        replace(
            with_choices(node("left"), goto("left", "join")),
            on_enter=effects({"op": "give", "item": "rope"}),
        ),
        with_choices(node("right"), goto("right", "join")),
        with_choices(
            node("join"),
            goto("join", "end", "Climb", condition="has(rope)"),
            goto("join", "end", "Open", condition="has(silver_key)"),
            goto("join", "end", "Recall", condition="flag(RAVEN)"),
        ),
        ending("end"),
    ]


def test_must_and_may_through_a_diamond() -> None:
    d = compute(book(*diamond(), items=ITEMS)).nodes
    assert d["left"].facts("item", "must") == ["rope"]
    assert d["join"].facts("flag", "must") == ["RAVEN"]
    assert d["join"].facts("item", "must") == []
    assert d["join"].facts("item", "may") == ["rope"]  # may = possibly, not definitely


def test_gate_verdicts_by_choice() -> None:
    nodes = diamond()
    nodes[3] = with_choices(
        node("join"),
        replace(goto("join", "end", "Climb", condition="has(rope)"), id="climb"),
        replace(goto("join", "end", "Open", condition="has(silver_key)"), id="open"),
        replace(goto("join", "end", "Recall", condition="flag(RAVEN)"), id="recall"),
        replace(goto("join", "end", "Either", condition="has(rope) or flag(RAVEN)"), id="either"),
        replace(goto("join", "end", "Not", condition="not flag(RAVEN)"), id="not"),
    )
    gates = compute(book(*nodes, items=ITEMS)).nodes["join"].gates
    assert gates == {
        "climb": None,  # depends on the path
        "open": False,  # nobody can have the key
        "recall": True,  # everyone has RAVEN
        "either": True,
        "not": False,
    }


def test_passing_a_condition_guarantees_its_facts() -> None:
    nodes = diamond()
    nodes[3] = with_choices(node("join"), goto("join", "end", "Climb", condition="has(rope)"))
    nodes[4] = with_choices(node("end"), goto("end", "fin"))
    d = compute(book(*nodes, ending("fin"), items=ITEMS)).nodes
    assert d["end"].facts("item", "must") == ["rope"]


def test_consumables_and_their_effects_are_only_may() -> None:
    b = book(
        replace(
            with_choices(node("start"), goto("start", "next")),
            on_enter=effects({"op": "give", "item": "potion"}),
        ),
        with_choices(node("next"), goto("next", "end")),
        ending("end"),
        items=ITEMS,
    )
    d = compute(b).nodes
    assert d["start"].facts("item", "must") == ["potion"]
    assert d["next"].facts("item", "may") == ["potion"]  # might have drunk it
    assert d["next"].facts("flag", "may") == ["DRANK"]


def test_loops_reach_a_fixpoint_and_unbounded_depth() -> None:
    b = book(
        with_choices(node("start"), goto("start", "loop")),
        replace(
            with_choices(node("loop"), goto("loop", "start", "Back"), goto("loop", "end")),
            on_enter=effects({"op": "set_flag", "flag": "LOOPED"}),
        ),
        ending("end"),
        items=ITEMS,
    )
    d = compute(b).nodes
    assert d["start"].facts("flag", "may") == ["LOOPED"]  # on a second visit
    assert d["loop"].facts("flag", "must") == ["LOOPED"]
    assert d["end"].depth_min == 2
    assert d["end"].depth_max is None  # the loop makes it unbounded
    assert d["start"].depth_max is None


def test_depths_and_canonical_predecessor() -> None:
    d = compute(book(*diamond(), items=ITEMS)).nodes
    assert (d["start"].depth_min, d["start"].depth_max) == (0, 0)
    assert (d["join"].depth_min, d["join"].depth_max) == (2, 2)
    assert d["join"].canonical_predecessor == "left"  # first choice wins ties
    assert d["end"].canonical_predecessor == "join"
    assert d["start"].canonical_predecessor is None


def test_unreachable_nodes_have_no_state() -> None:
    d = compute(book(*diamond(), with_choices(node("island"), goto("island", "end")), items=ITEMS))
    island = d.nodes["island"]
    assert not island.reachable
    assert island.state is None
    assert island.depth_min is None


def test_characters_met_and_tier_gated_choices() -> None:
    b = book(
        with_choices(
            node("start"),
            goto("start", "inn"),
            goto("start", "elite", min_tier="advanced"),
        ),
        replace(with_choices(node("inn"), goto("inn", "end")), character_ids=("c-mara",)),
        with_choices(node("elite"), goto("elite", "end")),
        ending("end"),
        items=ITEMS,
        characters=(Entity(id="c-mara", key="mara", name="Mara"),),
    )
    basic = compute(b, "basic").nodes
    assert not basic["elite"].reachable
    assert basic["end"].facts("character", "must") == ["mara"]
    advanced = compute(b, "advanced").nodes
    assert advanced["elite"].reachable
    assert advanced["end"].facts("character", "may") == ["mara"]


def test_impossible_choices_prove_nothing() -> None:
    """Passing has(silver_key) would 'give' the key; a never-taken edge must not."""
    b = book(
        with_choices(node("start"), goto("start", "hall")),
        with_choices(
            node("hall"),
            goto("hall", "start", "Unlock", condition="has(silver_key)"),
            goto("hall", "end"),
        ),
        ending("end"),
        items=ITEMS,
    )
    d = compute(b).nodes
    assert d["hall"].facts("item", "may") == []
    assert d["start"].facts("item", "may") == []


def test_once_only_gains_in_loops_are_not_guaranteed() -> None:
    """Review regression: a once-only give re-visited after a take isn't 'must'."""
    b = book(
        replace(
            with_choices(
                node("start"),
                goto("start", "pit"),
                replace(goto("start", "end", condition="not has(rope)"), id="free"),
            ),
            on_enter=effects({"op": "give", "item": "rope"}),
        ),
        replace(
            with_choices(node("pit"), goto("pit", "start")),
            on_enter=effects({"op": "take", "item": "rope"}),
        ),
        ending("end"),
        items=ITEMS,
    )
    d = compute(b).nodes["start"]
    assert d.facts("item", "may") == ["rope"]
    assert d.gates["free"] is None  # not "never": after the pit, the rope is gone


def test_impossible_choices_dont_shorten_routes() -> None:
    b = book(
        with_choices(
            node("start"),
            replace(goto("start", "x", condition="has(silver_key)"), id="shortcut"),
            goto("start", "a"),
        ),
        with_choices(node("a"), goto("a", "x")),
        with_choices(node("x"), goto("x", "end")),
        ending("end"),
        items=ITEMS,
    )
    d = compute(b).nodes
    assert (d["x"].depth_min, d["x"].canonical_predecessor) == (2, "a")


def test_only_reachable_through_impossible_choices_is_unreachable() -> None:
    b = book(
        with_choices(
            node("start"),
            replace(goto("start", "vault", condition="has(silver_key)"), id="locked"),
            goto("start", "end"),
        ),
        with_choices(node("vault"), goto("vault", "end")),
        ending("end"),
        items=ITEMS,
    )
    vault = compute(b).nodes["vault"]
    assert not vault.reachable
    assert vault.state is None


def test_consumables_drunk_mid_fight_and_flee_costs() -> None:
    from gamebook.core.model import Encounter, EncounterEnemy

    from .engine_book import choice

    start = replace(
        with_choices(
            node("start"),
            choice(
                "fight",
                "start",
                "combat",
                {"win": "won", "lose": "end", "flee": "fled"},
                encounter_id="enc",
                flee_allowed=True,
            ),
        ),
        on_enter=effects({"op": "give", "item": "potion"}, {"op": "give", "item": "rope"}),
        encounters=(Encounter("enc", "Orc", enemies=(EncounterEnemy("e-orc", level=1),)),),
    )
    b = book(
        start,
        with_choices(node("won"), goto("won", "end")),
        with_choices(node("fled"), goto("fled", "end")),
        ending("end"),
        items=ITEMS,
    )
    rules = b.rules
    assert rules is not None
    cost = list(effects({"op": "take", "item": "rope"}))
    tiers = [
        t.model_copy(update={"combat": t.combat.model_copy(update={"flee_cost": cost})})
        if t.parent is None
        else t
        for t in rules.tiers
    ]
    b = replace(b, rules=rules.model_copy(update={"tiers": tiers}))
    d = compute(b, "basic").nodes
    assert "potion" not in d["won"].facts("item", "must")  # may have drunk it fighting
    assert d["won"].facts("item", "must") == ["rope"]
    assert "rope" not in d["fled"].facts("item", "must")  # fleeing costs the rope
