import json
import os
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gamebook.core.engine import (
    Action,
    Game,
    GameError,
    LabEnemy,
    LabError,
    first_available,
    from_bundle,
    level_sweep,
    record,
    replay,
    rotating,
    simulate,
    to_bundle,
)
from gamebook.core.rules import default_rule_system

from .engine_book import engine_book

FIXED = {"SKILL": 9, "STAMINA": 18, "LUCK": 9, "GOLD": 10, "ARMOR": 0}


def game(tier: str = "basic", seed: int = 1, **start: object) -> Game:
    g = Game(engine_book(), tier, seed)
    g.start(**({"fixed_stats": dict(FIXED)} | start))  # type: ignore[arg-type]
    return g


def do(g: Game, type_: str, target: str | None = None) -> list[dict[str, object]]:
    return [e.to_dict() for e in g.step(Action(type_, target))]  # type: ignore[arg-type]


def labels(g: Game) -> list[str]:
    return [a.label for a in g.available()]


# ── creation ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("seed", range(20))
def test_rolled_stats_within_initial_ranges(seed: int) -> None:
    g = Game(engine_book(), "basic", seed)
    g.start()
    s = g.state.stats
    assert 7 <= s["SKILL"] <= 12
    assert 14 <= s["STAMINA"] <= 24
    assert s["GOLD"] == 10 + 1  # +1 on entering the start node
    assert g.state.max_stats["STAMINA"] == s["STAMINA"]
    assert "ARMOR" not in s  # medium+ only


def test_classes_grant_skills_at_advanced() -> None:
    g = game("advanced", character_class="rogue")
    assert g.state.character_class == "rogue"
    assert g.state.skills == {"STEALTH"}
    with pytest.raises(GameError, match="Unknown class"):
        game("advanced", character_class="wizard")


def test_start_requires_rules_and_tier() -> None:
    from dataclasses import replace

    with pytest.raises(GameError, match="rule system"):
        Game(replace(engine_book(), rules=None), "basic", 1)
    with pytest.raises(GameError, match="Unknown tier"):
        Game(engine_book(), "legendary", 1)


# ── nodes, effects, choices ─────────────────────────────────────────────


def test_on_enter_once_semantics_and_variants() -> None:
    g = game()
    assert g.state.items["potion"] == 2
    assert g.state.variant_id == "start-v"
    do(g, "choose", "start->market")
    do(g, "choose", "market->start")
    assert g.state.items["potion"] == 2  # give fires once
    assert g.state.stats["GOLD"] == 12  # once: false fires every visit
    assert g.state.variant_id == "start-back"  # visits(start) > 1
    assert g.state.visits["start"] == 2


def test_choice_visibility() -> None:
    g = game()
    actions = {a.target: a for a in g.actions() if a.type == "choose"}
    assert "start->vault" not in actions  # hidden: condition unmet
    assert actions["start->secret"].enabled is False  # show_disabled
    assert actions["start->secret"].reason == "Condition not met"
    assert "start->elite" not in actions  # advanced only
    assert "start->elite" in {a.target for a in game("advanced").available()}
    with pytest.raises(GameError, match="not available"):
        do(g, "choose", "start->secret")


def test_found_items_taken_once() -> None:
    g = game()
    assert "Take Rope" in labels(g)
    do(g, "take", "0")
    assert g.state.items["rope"] == 1
    assert "Take Rope" not in labels(g)


def test_roll_and_test_choices_are_seeded() -> None:
    outcomes = set()
    for seed in range(30):
        g = game(seed=seed)
        do(g, "choose", "start->hall")
        events = do(g, "choose", "gamble")
        roll = next(e for e in events if e["type"] == "roll")
        total = roll["total"]
        assert isinstance(total, int)
        assert g.node is not None
        assert g.node.key == ("trap" if total <= 6 else "den")
        outcomes.add(g.node.key)
    assert outcomes == {"trap", "den"}


def test_luck_test_spends_luck() -> None:
    g = game(seed=4)
    do(g, "choose", "start->hall")
    events = do(g, "choose", "luck")
    test = next(e for e in events if e["type"] == "test")
    assert test["success"] == (int(str(test["roll"])) <= 9)
    assert g.state.stats["LUCK"] == 8


def test_effect_defeat_and_clamping() -> None:
    # Find a seed whose gamble rolls low, sending the 3-STAMINA reader into the trap.
    for seed in range(50):
        g = game(seed=seed, fixed_stats={**FIXED, "STAMINA": 3})
        do(g, "choose", "start->hall")
        do(g, "choose", "gamble")
        assert g.node is not None
        if g.node.key == "trap":
            assert g.state.ended == "defeated"
            assert g.state.stats["STAMINA"] == 0  # clamped at min
            break
    else:
        pytest.fail("no low roll found")


def test_consumables_respect_max() -> None:
    g = game(fixed_stats={**FIXED, "STAMINA": 18})
    g.state.stats["STAMINA"] = 16
    do(g, "use", "potion")
    assert g.state.stats["STAMINA"] == 18  # max is the initial value
    assert g.state.items["potion"] == 1


# ── shop & equipment ────────────────────────────────────────────────────


def test_shop_buy_sell_and_stock() -> None:
    g = game()
    do(g, "take", "0")  # rope (value 6)
    do(g, "choose", "start->market")
    acts = {a.label: a for a in g.actions()}
    assert acts["Buy Iron Key (50)"].enabled is False
    assert acts["Buy Iron Key (50)"].reason == "Not enough money"
    do(g, "buy", "0")  # sword for 8
    assert g.state.stats["GOLD"] == 11 - 8
    assert g.state.items["sword"] == 1
    sold_out = next(a for a in g.actions() if a.label.startswith("Buy Sword"))
    assert (sold_out.enabled, sold_out.reason) == (False, "Sold out")
    do(g, "sell", "rope")
    assert g.state.stats["GOLD"] == 3 + 3  # 50% of 6
    assert "rope" not in g.state.to_dict()["items"]


def test_equipment_modifiers_follow_tier() -> None:
    for tier, bonus in (("basic", 0), ("medium", 2)):
        g = game(tier)
        g.state.items["sword"] = 1
        if tier == "basic":
            assert not any(a.type == "equip" for a in g.available())  # no slots in basic
            g.state.equipped["weapon"] = "sword"
        else:
            do(g, "equip", "sword")
        assert g.stat("SKILL") == 9 + bonus
    g = game("medium")
    g.state.items["sword"] = 1
    do(g, "equip", "sword")
    do(g, "unequip", "weapon")
    assert g.stat("SKILL") == 9


# ── combat ──────────────────────────────────────────────────────────────


def fight_until_over(g: Game) -> None:
    while g.state.combat is not None:
        do(g, "attack")


def test_combat_win_and_lose_routes() -> None:
    results = {}
    for seed in range(40):
        g = game(seed=seed, fixed_stats={**FIXED, "SKILL": 7, "STAMINA": 6})
        do(g, "choose", "start->hall")
        do(g, "choose", "fight")
        assert g.state.combat is not None
        assert [e.key for e in g.state.combat.enemies] == ["orc"]
        assert g.state.combat.enemies[0].stats == {"SKILL": 7, "STAMINA": 8}
        fight_until_over(g)
        assert g.node is not None
        results[g.node.key] = seed
        if g.node.key == "dead":
            assert g.state.ended == "death"
    assert set(results) == {"den", "dead"}


def test_flee_costs_stamina() -> None:
    g = game()
    do(g, "choose", "start->hall")
    do(g, "choose", "fight")
    do(g, "flee")
    assert g.node is not None
    assert g.node.key == "start"
    assert g.state.stats["STAMINA"] == 16
    assert g.state.combat is None


def test_table_encounters() -> None:
    kinds = set()
    for seed in range(40):
        g = game(seed=seed)
        g.state.node_id = "den"
        events = do(g, "choose", "rats")
        table = next(e for e in events if e["type"] == "table")
        kinds.add(table["result"])
        if table["result"] == "enemies":
            assert g.state.combat is not None
            assert [e.key for e in g.state.combat.enemies] == ["rat#1", "rat#2"]
        else:
            assert any(e["type"] == "combat_skipped" for e in events)
            assert g.state.ended == "victory"
    assert kinds == {"nothing", "item", "enemies"}


def test_simultaneous_fight_and_stalemate_cap() -> None:
    g = game("medium", fixed_stats={**FIXED, "SKILL": 30, "STAMINA": 999, "ARMOR": 999})
    g.state.node_id = "den"
    do(g, "choose", "wall")
    assert g.state.combat is not None
    assert g.state.combat.simultaneous
    fight_until_over(g)
    assert any(e.type == "combat_stalemate" for e in g.log)
    assert g.node is not None
    assert g.node.key == "dead"


def test_game_over_is_final() -> None:
    g = game()
    do(g, "choose", "start->hall")
    g.state.node_id = "vault"
    do(g, "choose", "vault->end")
    assert g.state.ended == "victory"
    assert g.available() == []
    with pytest.raises(GameError, match="over"):
        do(g, "choose", "x")


def test_stuck_when_destination_missing() -> None:
    from dataclasses import replace

    b = engine_book()
    nodes = tuple(
        replace(n, choices=tuple(replace(c, outcomes=()) for c in n.choices))
        if n.key == "market"
        else n
        for n in b.nodes
    )
    g = Game(replace(b, nodes=nodes), "basic", 1)
    g.start(fixed_stats=dict(FIXED))
    do(g, "choose", "start->market")
    assert g.state.ended is None  # the shop still works
    do(g, "choose", "market->start")
    assert g.state.ended == "stuck"
    assert "no destination" in str(g.log[-1].data["reason"])


def test_content_errors_become_events() -> None:
    from dataclasses import replace

    b = engine_book()
    nodes = tuple(
        replace(
            n, choices=(replace(n.choices[0], condition="1 / (GOLD - GOLD) > 0"), *n.choices[1:])
        )
        if n.key == "start"
        else n
        for n in b.nodes
    )
    g = Game(replace(b, nodes=nodes), "basic", 1)
    g.start(fixed_stats=dict(FIXED))
    assert any(e.type == "error" and "division by zero" in str(e.data["message"]) for e in g.log)
    assert "start->market" not in {a.target for a in g.available()}


# ── determinism & invariants ────────────────────────────────────────────


def random_playthrough(seed: int, picks: list[int], tier: str) -> Game:
    g = Game(engine_book(), tier, seed)
    g.start()
    for p in picks:
        options = g.available()
        if g.state.ended or not options:
            break
        g.step(options[p % len(options)])
    return g


@given(
    st.integers(0, 10_000),
    st.lists(st.integers(0, 50), max_size=60),
    st.sampled_from(["basic", "medium", "advanced"]),
)
@settings(max_examples=150, deadline=None)
def test_games_are_deterministic_and_respect_bounds(seed: int, picks: list[int], tier: str) -> None:
    a = random_playthrough(seed, picks, tier)
    b = random_playthrough(seed, picks, tier)
    assert [e.to_dict() for e in a.log] == [e.to_dict() for e in b.log]
    assert a.state.to_dict() == b.state.to_dict()
    for key, value in a.state.stats.items():
        sd = a.tier.stats[key]
        if sd.min is not None:
            assert value >= sd.min
        if key in a.state.max_stats:
            assert value <= a.state.max_stats[key]
    assert all(v >= 0 for v in a.state.items.values())
    assert json.dumps(a.state.to_dict())  # serialisable


# ── bundle & golden traces ──────────────────────────────────────────────


def test_bundle_round_trip() -> None:
    b = engine_book()
    bundle = to_bundle(b)
    assert from_bundle(json.loads(json.dumps(bundle))) == b
    with pytest.raises(ValueError, match="bundle"):
        from_bundle({"format": "nope"})


GOLDEN = Path(__file__).parent / "golden"
GOLDEN_CASES = [
    ("basic", 11, {}),
    ("basic", 12, {}),
    ("medium", 22, {}),
    ("medium", 23, {}),
    ("advanced", 33, {"character_class": "ranger"}),
    ("advanced", 34, {"character_class": "rogue"}),
]


def test_golden_traces_cover_the_engine() -> None:
    """The pinned traces together exercise every kind of event."""
    kinds: set[str] = set()
    for tier, seed, creation in GOLDEN_CASES:
        trace = record(engine_book(), tier, seed, creation=creation, policy=rotating, max_steps=120)
        kinds |= {e["type"] for e in trace["events"]}
    assert kinds >= {
        "roll",
        "character_created",
        "enter",
        "effect",
        "action",
        "outcome",
        "test",
        "combat_start",
        "combat_round",
        "combat_end",
        "item_taken",
        "game_over",
    }
    assert first_available(Game(engine_book(), "basic", 1)) is None  # not started yet


@pytest.mark.parametrize(("tier", "seed", "creation"), GOLDEN_CASES)
def test_golden_traces(tier: str, seed: int, creation: dict[str, object]) -> None:
    """Engine behaviour is pinned. Regenerate deliberately with GOLDEN_UPDATE=1."""
    path = GOLDEN / f"engine-{tier}-{seed}.json"
    trace = record(engine_book(), tier, seed, creation=creation, policy=rotating, max_steps=120)
    if os.environ.get("GOLDEN_UPDATE") or not path.exists():
        path.write_text(json.dumps(trace, indent=1, sort_keys=True) + "\n")
    expected = json.loads(path.read_text())
    assert json.loads(json.dumps(trace)) == expected, (
        "engine behaviour changed (GOLDEN_UPDATE=1 to accept)"
    )
    assert replay(expected) == {
        "events": expected["events"],
        "final_state": expected["final_state"],
    }


# ── combat lab ──────────────────────────────────────────────────────────


def test_lab_is_deterministic_and_sensible() -> None:
    rules = default_rule_system()
    orc = [LabEnemy("Orc", {"SKILL": 8, "STAMINA": 10})]
    a = simulate(rules, "basic", orc, runs=500, seed=5).summary()
    assert a == simulate(rules, "basic", orc, runs=500, seed=5).summary()
    assert a["wins"] + a["losses"] + a["stalemates"] == 500  # type: ignore[operator]
    weak = simulate(
        rules, "basic", orc, runs=1000, seed=1, player_stats={"SKILL": 6, "STAMINA": 12}
    ).win_rate
    strong = simulate(
        rules, "basic", orc, runs=1000, seed=1, player_stats={"SKILL": 11, "STAMINA": 12}
    ).win_rate
    assert strong > weak + 0.3
    one = simulate(rules, "basic", orc, runs=1000, seed=2).win_rate
    two = simulate(
        rules,
        "basic",
        [LabEnemy("Orc", {"SKILL": 8, "STAMINA": 10}, count=2)],
        runs=1000,
        seed=2,
        simultaneous=True,
    ).win_rate
    assert two < one


def test_lab_level_sweep_gets_harder() -> None:
    points = level_sweep(
        default_rule_system(),
        "medium",
        "Orc",
        {"SKILL": "5 + level", "STAMINA": "4 + level * 2", "ARMOR": "floor(level / 2)"},
        range(1, 9),
        runs=400,
        seed=3,
    )
    rates = [p.win_rate for p in points]
    assert rates[0] > 0.9
    assert rates[-1] < 0.2
    assert points[3].enemy == {"SKILL": 9, "STAMINA": 12, "ARMOR": 2}


def test_lab_crits_hurt_more_at_advanced() -> None:
    rules = default_rule_system()
    foe = [LabEnemy("Duelist", {"SKILL": 9, "STAMINA": 12, "ARMOR": 0})]
    player = {"SKILL": 9, "STAMINA": 12, "LUCK": 9, "GOLD": 0, "ARMOR": 0}
    medium = simulate(rules, "medium", foe, runs=2000, seed=9, player_stats=player).summary()
    advanced = simulate(rules, "advanced", foe, runs=2000, seed=9, player_stats=player).summary()
    assert advanced["rounds"]["mean"] < medium["rounds"]["mean"]  # type: ignore[index]


def test_lab_errors() -> None:
    rules = default_rule_system()
    with pytest.raises(LabError, match="Runs"):
        simulate(rules, "basic", [LabEnemy("x", {})], runs=0)
    with pytest.raises(LabError, match="enemy"):
        simulate(rules, "basic", [])
    rules.tiers[0].combat.player_attack = None
    with pytest.raises(LabError, match="combat"):
        simulate(rules, "basic", [LabEnemy("x", {})])
