"""Regressions for the Phase 3 review findings (one test per finding)."""

import time
from dataclasses import replace

import pytest

from gamebook.core import gbx
from gamebook.core.engine import Action, Game, LabEnemy, LabError, from_bundle, simulate, to_bundle
from gamebook.core.model import (
    Choice,
    Encounter,
    EncounterEnemy,
    Enemy,
    Item,
    ItemModifier,
    Outcome,
    Placement,
    ShopEntry,
)
from gamebook.core.rules import CombatDef, StatDef, default_rule_system

from .builders import book, ending, goto, node, with_choices

FIXED = {"SKILL": 9, "STAMINA": 6, "LUCK": 9, "GOLD": 10}


def fight_book(**rules_changes: object) -> Game:
    rules = default_rule_system()
    for k, v in rules_changes.items():
        setattr(rules.tiers[0].combat, k, v)
    fight = Choice(
        id="f",
        node_id="start",
        label="Fight",
        kind="combat",
        encounter_id="enc",
        outcomes=(Outcome("w", "win", "end"), Outcome("l", "lose", "dead")),
    )
    b = book(
        replace(
            with_choices(node("start"), fight),
            encounters=(Encounter("enc", "Giant", enemies=(EncounterEnemy("e-giant"),)),),
        ),
        ending("end"),
        ending("dead", kind="death"),
        rules=rules,
        items=(
            Item(
                id="i-amulet",
                key="amulet",
                name="Amulet",
                modifiers=(ItemModifier("STAMINA", "3"),),
            ),
        ),
        enemies=(
            Enemy(
                id="e-giant",
                key="giant",
                name="Giant",
                stat_formulas={"SKILL": "30", "STAMINA": "50"},
            ),
        ),
    )
    g = Game(b, "basic", 1)
    g.start(fixed_stats=dict(FIXED))
    return g


def test_1_item_bonus_on_damage_stat_does_not_make_player_unkillable() -> None:
    g = fight_book()
    g.state.items["amulet"] = 1
    g.step(Action("choose", "f"))
    while g.state.combat is not None:
        g.step(Action("attack"))
    assert not any(e.type == "combat_stalemate" for e in g.log)
    assert g.state.ended == "death"
    assert g.state.stats["STAMINA"] == 0


def test_2_not_stuck_while_an_item_can_unlock_the_exit() -> None:
    b = book(
        replace(
            with_choices(node("start"), goto("start", "end", "Unlock", condition="has(iron_key)")),
            items=(Placement("i-key"),),
        ),
        ending("end"),
        items=(Item(id="i-key", key="iron_key", name="Iron Key", category="key"),),
    )
    g = Game(b, "basic", 1)
    g.start(fixed_stats=dict(FIXED))
    assert g.state.ended is None
    g.step(Action("take", "0"))
    g.step(Action("choose", "start->end"))
    assert g.state.ended == "victory"
    # With nothing at all left to do, the game is stuck.
    b2 = book(
        with_choices(node("start"), goto("start", "end", "Unlock", condition="has(iron_key)")),
        ending("end"),
    )
    g2 = Game(b2, "basic", 1)
    g2.start(fixed_stats=dict(FIXED))
    assert g2.state.ended == "stuck"


@pytest.mark.parametrize(
    ("changes", "message"),
    [({"damage": "10 / enemy.ARMOR"}, "division by zero"), ({"player_attack": "2d6 +"}, "")],
)
def test_3_combat_content_errors_become_events(changes: dict[str, object], message: str) -> None:
    g = fight_book(**changes)
    if g.combat_rules is None:  # unparseable rules: reported, combat skipped
        assert any(e.type == "error" and e.data["where"] == "combat rules" for e in g.log)
        g.step(Action("choose", "f"))
        assert any(e.type == "combat_unconfigured" for e in g.log)
        return
    g.step(Action("choose", "f"))
    for _ in range(50):
        if g.state.combat is None:
            break
        g.step(Action("attack"))
    assert g.state.ended == "stuck"
    assert any(e.type == "error" and message in str(e.data["message"]) for e in g.log)


def test_3_lab_content_errors_are_lab_errors() -> None:
    rules = default_rule_system()
    rules.tiers[0].combat.damage = "10 / enemy.ARMOR"
    rules.tiers[0].stats.append(
        StatDef(key="ARMOR", label="Armour", applies_to=["player", "enemy"])
    )
    with pytest.raises(LabError, match="division by zero"):
        simulate(rules, "basic", [LabEnemy("x", {"SKILL": 1, "STAMINA": 5, "ARMOR": 0})], runs=10)
    bad = default_rule_system()
    bad.tiers[0].stats[0].initial = "has(x)"
    with pytest.raises(LabError):
        simulate(bad, "basic", [LabEnemy("x", {"SKILL": 1, "STAMINA": 5})], runs=10)
    unparsable = default_rule_system()
    unparsable.tiers[0].combat = CombatDef(
        player_attack="2d6 +", enemy_attack="2d6", damage_stat="STAMINA"
    )
    with pytest.raises(LabError, match="parse"):
        simulate(unparsable, "basic", [LabEnemy("x", {})], runs=10)


@pytest.mark.parametrize("src", ["floor() > 0", "clamp(1) > 0", "min() > 0", "max(1) > 0"])
def test_4_wrong_arity_is_an_eval_error(src: str) -> None:
    from gamebook.core.gbx.compiler import compile_expr

    e = gbx.parse(src)
    with pytest.raises(gbx.GbxEvalError):
        gbx.evaluate(e, gbx.SimpleEnv())
    with pytest.raises(gbx.GbxEvalError):
        compile_expr(e)(gbx.SimpleEnv(), None)
    b = book(
        with_choices(
            node("start"), goto("start", "end", condition=src), goto("start", "end", "Other")
        ),
        ending("end"),
    )
    g = Game(b, "basic", 1)
    g.start(fixed_stats=dict(FIXED))  # no crash
    assert any(e.type == "error" for e in g.log)


def test_5_clamp_draws_dice_in_source_order() -> None:
    from gamebook.core.gbx.compiler import compile_expr

    e = gbx.parse("clamp(1d6, 1d100, 1d1000)")
    for seed in range(20):
        assert gbx.evaluate(e, gbx.SimpleEnv(), gbx.SeededRng(seed)) == compile_expr(e)(
            gbx.SimpleEnv(), gbx.SeededRng(seed)
        )


def test_6_queries_do_not_write_to_the_log() -> None:
    b = book(
        with_choices(
            node("start"),
            goto("start", "end", condition="1 / 0 > 1"),
            goto("start", "end", "Other"),
        ),
        ending("end"),
    )
    g = Game(b, "basic", 1)
    g.start(fixed_stats=dict(FIXED))
    errors = sum(e.type == "error" for e in g.log)
    assert errors == 1  # reported once, on arrival
    before = len(g.log)
    g.actions()
    g.available()
    g.actions()
    assert len(g.log) == before


def shop_game(*, rules_without_gold: bool = False, potion_stack: int | None = None) -> Game:
    rules = default_rule_system()
    if rules_without_gold:
        rules.tiers[0].stats = [s for s in rules.tiers[0].stats if s.key != "GOLD"]
    b = book(
        replace(
            with_choices(node("start"), goto("start", "end")),
            shop=(ShopEntry("i-potion", price=1),),
            shop_sell_rate=50,
        ),
        ending("end"),
        rules=rules,
        items=(
            Item(id="i-rope", key="rope", name="Rope", value=6),
            Item(
                id="i-potion",
                key="potion",
                name="Potion",
                category="consumable",
                max_stack=potion_stack,
            ),
        ),
    )
    g = Game(b, "basic", 1)
    g.start(
        fixed_stats={k: v for k, v in FIXED.items() if not (rules_without_gold and k == "GOLD")}
    )
    return g


def test_7_no_selling_without_a_currency() -> None:
    g = shop_game(rules_without_gold=True)
    g.state.items["rope"] = 1
    assert not any(a.type == "sell" for a in g.actions())


def test_8_cannot_buy_past_max_stack() -> None:
    g = shop_game(potion_stack=1)
    g.state.items["potion"] = 1
    buy = next(a for a in g.actions() if a.type == "buy")
    assert (buy.enabled, buy.reason) == (False, "Can't carry more")


def test_9_no_minimum_survives_bundles() -> None:
    rules = default_rule_system()
    rules.tiers[0].stats[0].min = None
    b = book(with_choices(node("start"), goto("start", "end")), ending("end"), rules=rules)
    assert from_bundle(to_bundle(b)) == b


def test_11_lab_work_is_bounded() -> None:
    rules = default_rule_system()
    wall = [LabEnemy("Wall", {"SKILL": 0, "STAMINA": 10**9}, count=10)]
    immortal = {"SKILL": 0, "STAMINA": 10**9}
    r = simulate(
        rules,
        "basic",
        wall,
        runs=20_000,
        seed=1,
        player_stats=immortal,
        simultaneous=True,
        max_work=50_000,
    )
    assert r.truncated
    assert 0 < r.runs < 20_000
    assert r.summary()["truncated"] is True
    # The default budget keeps a worst-case request to seconds, not minutes.
    start = time.perf_counter()
    simulate(rules, "basic", wall, runs=20_000, seed=1, player_stats=immortal, simultaneous=True)
    assert time.perf_counter() - start < 20


def test_consumable_that_defeats_mid_fight_ends_the_game() -> None:
    g = fight_book()
    g.step(Action("choose", "f"))
    g.state.stats["STAMINA"] = 1
    from gamebook.core.effects import ModifyStat

    g._items["poison"] = Item(
        id="i-poison",
        key="poison",
        name="Poison",
        category="consumable",
        use_effects=(ModifyStat(stat="STAMINA", amount="-5"),),
    )
    g.state.items["poison"] = 1
    g.step(Action("use", "poison"))
    assert g.state.ended == "defeated"
    assert g.state.combat is None
