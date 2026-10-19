"""Class bonuses, starting gear, experience and levels."""

from __future__ import annotations

from dataclasses import replace

import pytest

from gamebook.core.analysis import validate_book, validate_rule_system
from gamebook.core.effects import ChooseClass, ModifyStat
from gamebook.core.engine import Action, Game
from gamebook.core.engine.narrate import Names, narrate
from gamebook.core.model import BookSnapshot
from gamebook.core.rules import (
    ProgressionDef,
    RuleSystemDef,
    StartingItem,
    StatBonus,
    default_rule_system,
    effective_tier,
    tier_view,
)

from .builders import effects
from .engine_book import engine_book

FIXED = {"SKILL": 9, "STAMINA": 18, "LUCK": 9, "GOLD": 10, "ARMOR": 0, "XP": 0, "LEVEL": 1}


def rules_with(**tiers: dict[str, object]) -> RuleSystemDef:
    """The default rules with some tier fields replaced."""
    base = default_rule_system()
    return RuleSystemDef(
        tiers=[t.model_copy(update=tiers.get(t.key, {})) for t in base.tiers],
    )


def prog(**fields: object) -> ProgressionDef:
    """The default (medium) levelling with some fields changed."""
    return default_rule_system().tiers[1].progression.model_copy(update=fields)


def book_with(rules: RuleSystemDef) -> BookSnapshot:
    return replace(engine_book(), rules=rules)


def start(
    book: BookSnapshot, tier: str = "medium", seed: int = 1, **kw: object
) -> tuple[Game, list[dict[str, object]]]:
    g = Game(book, tier, seed)
    events = g.start(**({"fixed_stats": dict(FIXED)} | kw))  # type: ignore[arg-type]
    return g, [e.to_dict() for e in events]


def do(g: Game, type_: str, target: str | None = None) -> list[dict[str, object]]:
    return [e.to_dict() for e in g.step(Action(type_, target))]  # type: ignore[arg-type]


def win_orc_fight(g: Game) -> list[dict[str, object]]:
    """Fight the level-2 orc in the hall until the fight ends; returns the events."""
    do(g, "choose", "start->hall")
    events = do(g, "choose", "fight")
    while g.state.combat is not None:
        events += do(g, "attack")
    return events


# ── classes ─────────────────────────────────────────────────────────────


def test_class_bonuses_raise_stats_and_starting_maximums() -> None:
    g, events = start(engine_book(), "advanced", character_class="scholar")
    assert g.state.stats["LUCK"] == 9 + 1
    assert g.state.stats["STAMINA"] == 18 + 2
    assert g.state.max_stats["STAMINA"] == 20  # max is the starting value, so it moves too
    created = next(e for e in events if e["type"] == "character_created")
    assert created["stats"]["STAMINA"] == 20  # type: ignore[index]

    g, _ = start(engine_book(), "advanced", character_class="ranger")
    assert g.state.stats["SKILL"] == 10
    assert g.state.max_stats["SKILL"] == 10


def test_class_bonus_can_roll_and_ignores_unknown_stats() -> None:
    rules = default_rule_system()
    adv = rules.tiers[2]
    adv.classes[0].modifiers = [
        StatBonus(stat="GOLD", amount="1d6"),
        StatBonus(stat="NOPE", amount="5"),
    ]
    g, _ = start(book_with(rules), "advanced", character_class="ranger")
    assert 11 <= g.state.stats["GOLD"] <= 17 + 1  # +1 on entering the start node
    assert "NOPE" not in g.state.stats


# ── starting gear ───────────────────────────────────────────────────────


def test_starting_items_from_tiers_and_class() -> None:
    rules = rules_with(
        basic={"starting_items": [StartingItem(item="potion", qty=2)]},
        medium={"starting_items": [StartingItem(item="sword", equip=True)]},
    )
    rules.tiers[2].classes[1].starting_items = [StartingItem(item="rope")]
    g, events = start(book_with(rules), "advanced", character_class="rogue")
    # Basic's potions, plus 2 more from the start node.
    assert g.state.items == {"potion": 4, "sword": 1, "rope": 1}
    assert g.state.equipped == {"weapon": "sword"}
    assert g.stat("SKILL") == 9 + 2  # the sword counts at once
    gear = [e for e in events if e.get("source") == "start"]
    assert [(e["op"], e["item"]) for e in gear] == [
        ("give", "potion"),
        ("give", "sword"),
        ("equip", "sword"),
        ("give", "rope"),
    ]

    # Basic has no slots: the sword is carried, not equipped.
    g, _ = start(book_with(rules), "basic")
    assert "sword" not in g.state.items
    g, _ = start(
        book_with(rules_with(basic={"starting_items": [StartingItem(item="sword", equip=True)]})),
        "basic",
    )
    assert g.state.items["sword"] == 1
    assert g.state.equipped == {}


def test_unknown_starting_item_is_a_content_error() -> None:
    rules = rules_with(basic={"starting_items": [StartingItem(item="ghost")]})
    g, events = start(book_with(rules), "basic")
    assert {"type": "error", "where": "starting items", "message": "unknown item ghost"} in events
    assert "ghost" not in g.state.items


# ── experience ──────────────────────────────────────────────────────────


def test_winning_a_fight_awards_xp_by_relative_level() -> None:
    for seed in range(40):
        g, _ = start(engine_book(), seed=seed, fixed_stats={**FIXED, "SKILL": 12})
        events = win_orc_fight(g)
        if g.node is not None and g.node.key == "den":
            break
    else:
        pytest.fail("never won")
    gained = [e for e in events if e["type"] == "xp_gained"]
    # One level-2 orc against a level-1 reader: max(1, 10 + 5 * (2 - 1)).
    assert gained == [{"type": "xp_gained", "stat": "XP", "amount": 15, "value": 15}]
    event = next(e for e in g.log if e.type == "xp_gained")
    assert narrate(event, Names.for_game(g)) == "Gained 15 Experience (now 15)"

    # A stronger reader earns less for the same orc (never below 1).
    g, _ = start(engine_book(), seed=seed, fixed_stats={**FIXED, "SKILL": 12, "LEVEL": 6})
    events = win_orc_fight(g)
    assert [e["amount"] for e in events if e["type"] == "xp_gained"] == [1]


def test_no_xp_for_fleeing_losing_or_basic() -> None:
    g, _ = start(engine_book())
    do(g, "choose", "start->hall")
    do(g, "choose", "fight")
    assert not any(e["type"] == "xp_gained" for e in do(g, "flee"))
    g, _ = start(engine_book(), fixed_stats={**FIXED, "SKILL": 1, "STAMINA": 1})
    assert not any(e["type"] == "xp_gained" for e in win_orc_fight(g))
    assert g.state.ended == "death"
    g, _ = start(engine_book(), "basic", fixed_stats={**FIXED, "SKILL": 12})
    assert not any(e["type"] == "xp_gained" for e in win_orc_fight(g))


def test_level_up_spends_xp_and_applies_bonuses() -> None:
    g, _ = start(engine_book())
    g._apply([_modify("XP", "250")], "test")
    # 100 for level 2, then 200 for level 3 is too much: 150 left.
    assert g.state.stats["LEVEL"] == 2
    assert g.state.stats["XP"] == 150
    assert g.state.stats["STAMINA"] == 18 + 2
    assert g.state.max_stats["STAMINA"] == 20
    assert g.state.stats["SKILL"] == 9  # SKILL only every third level
    g._apply([_modify("XP", "50")], "test")
    assert g.state.stats["LEVEL"] == 3
    assert g.state.stats["SKILL"] == 10
    assert g.state.max_stats["SKILL"] == 10
    ups = [e.to_dict() for e in g.log if e.type == "level_up"]
    assert ups == [
        {"type": "level_up", "stat": "LEVEL", "level": 2, "xp": 150},
        {"type": "level_up", "stat": "LEVEL", "level": 3, "xp": 0},
    ]
    assert narrate(next(e for e in g.log if e.type == "level_up"), Names.for_game(g)) == (
        "Level up! Level 2"
    )
    assert g.xp_needed() == 300


def test_highest_level_and_broken_formulas_stop_levelling() -> None:
    g, _ = start(engine_book(), fixed_stats={**FIXED, "LEVEL": 10})
    g._apply([_modify("XP", "5000")], "test")
    assert g.state.stats["LEVEL"] == 10
    assert g.xp_needed() is None

    # A formula that makes levels free must not loop forever.
    rules = rules_with(medium={"progression": prog(xp_to_next="0", max_level=None)})
    g, _ = start(book_with(rules))
    g._apply([_modify("XP", "5")], "test")
    assert g.state.stats["LEVEL"] == 1

    rules = rules_with(medium={"progression": prog(xp_to_next="level - 100 + XP", max_level=None)})
    g, _ = start(book_with(rules))
    g._apply([_modify("XP", "1000")], "test")
    assert 1 < g.state.stats["LEVEL"] <= 101  # capped by MAX_LEVEL_UPS per check

    rules = rules_with(medium={"progression": prog(xp_to_next="1d6")})
    g, _ = start(book_with(rules))
    g._apply([_modify("XP", "500")], "test")
    assert g.state.stats["LEVEL"] == 1
    assert any(e.type == "error" and e.data["where"] == "XP for the next level" for e in g.log)


def test_progression_inherits_field_by_field() -> None:
    rules = rules_with(advanced={"progression": ProgressionDef(xp_to_next="50 * level")})
    eff = effective_tier(rules, "advanced")
    assert eff.progression.xp_stat == "XP"
    assert eff.progression.xp_to_next == "50 * level"
    assert eff.progression.xp_award == "max(1, 10 + 5 * (enemy_level - level))"
    assert not effective_tier(rules, "basic").progression.enabled()
    view = tier_view(rules, "advanced")
    assert view["progression_origin"] == {
        "xp_stat": "medium",
        "level_stat": "medium",
        "xp_award": "medium",
        "xp_to_next": "advanced",
        "max_level": "medium",
        "level_up": "medium",
    }


# ── validation ──────────────────────────────────────────────────────────


def test_rule_validation_checks_bonuses_gear_and_levels() -> None:
    rules = rules_with(
        basic={"starting_items": [StartingItem(item="ghost")]},
        medium={
            "progression": ProgressionDef(
                xp_stat="XP",
                level_stat="NOPE",
                xp_award="enemy_level +",
                xp_to_next="100 * level",
                level_up=[StatBonus(stat="ARMOR", amount="nonsense")],
            )
        },
    )
    rules.tiers[2].classes[0].modifiers = [StatBonus(stat="WISDOM", amount="1")]
    codes = {(p.code, p.message) for p in validate_rule_system(rules)}
    messages = " | ".join(m for _, m in codes)
    assert "the level stat 'NOPE' isn't a player stat" in messages
    assert "class 'Ranger': unknown player stat 'WISDOM'" in messages
    assert any(c.startswith("gbx.") and "XP award" in m for c, m in codes)
    assert any(c.startswith("gbx.") and "level-up bonus ARMOR" in m for c, m in codes)
    assert not any(c == "unknown_item" for c, _ in codes)  # no book: items unchecked

    book_codes = {p.code for p in validate_book(book_with(rules))}
    assert "unknown_item" in book_codes

    half = rules_with(medium={"progression": ProgressionDef(xp_stat="XP")})
    assert "progression_incomplete" in {p.code for p in validate_rule_system(half)}
    assert not [p for p in validate_rule_system(default_rule_system()) if p.severity == "error"]


def _modify(stat: str, amount: str) -> ModifyStat:
    return ModifyStat(op="modify", stat=stat, amount=amount)


def test_capped_level_stat_is_warned_and_shows_no_next_level() -> None:
    rules = default_rule_system()
    level = next(s for s in rules.tiers[1].stats if s.key == "LEVEL")
    level.max = 1
    assert "progression_capped" not in {p.code for p in validate_rule_system(rules)}
    level.max_is_initial = True
    assert "progression_capped" in {p.code for p in validate_rule_system(rules)}
    g, _ = start(book_with(rules))
    assert g.xp_needed() is None
    g._apply([_modify("XP", "500")], "test")
    assert g.state.stats["LEVEL"] == 1


# ── choosing a class in the story ───────────────────────────────────────


def story_book(*, on_hall: list[dict[str, object]] | None = None) -> BookSnapshot:
    """Advanced picks classes in the story; entering the hall asks for one."""
    rules = default_rule_system()
    rules.tiers[2].class_choice = "story"
    rules.tiers[2].classes[0].starting_items = [StartingItem(item="rope")]
    b = book_with(rules)
    hall = on_hall if on_hall is not None else [{"op": "choose_class"}]
    return replace(
        b,
        nodes=tuple(
            replace(n, on_enter=(*n.on_enter, *effects(*hall))) if n.key == "hall" else n
            for n in b.nodes
        ),
    )


def test_class_is_picked_in_the_story() -> None:
    g, events = start(story_book(), "advanced", character_class="ranger")
    assert g.state.character_class is None  # ignored: this tier picks in the story
    assert g.state.skills == set()
    assert next(e for e in events if e["type"] == "character_created")["class"] is None

    entered = do(g, "choose", "start->hall")
    assert g.state.class_pending == ["ranger", "rogue", "scholar"]
    assert g.node is not None
    effect: dict[str, object] = {
        "type": "effect",
        "source": f"enter:{g.node.id}",
        "op": "choose_class",
        "classes": ["ranger", "rogue", "scholar"],
    }
    assert effect in entered
    # Nothing else can be done until a class is picked.
    assert [(a.type, a.target, a.label) for a in g.available()] == [
        ("choose_class", "ranger", "Become a Ranger"),
        ("choose_class", "rogue", "Become a Rogue"),
        ("choose_class", "scholar", "Become a Scholar"),
    ]
    picked = do(g, "choose_class", "ranger")
    assert g.state.class_pending is None
    assert g.state.character_class == "ranger"
    assert g.state.skills == {"TRACKING", "ARCHERY"}
    assert g.state.stats["SKILL"] == 10
    assert g.state.items["rope"] == 1
    assert {"type": "class_chosen", "class": "ranger"} in picked
    names = Names.for_game(g)
    assert [narrate(e, names) for e in g.log if e.type == "class_chosen"] == [
        "You are now a Ranger"
    ]
    assert "fight" in {a.target for a in g.available()}  # the hall's choices are back
    assert g.holds("class(ranger)")


def test_class_choice_offers_a_subset_and_happens_once() -> None:
    g, _ = start(
        story_book(on_hall=[{"op": "choose_class", "classes": ["rogue", "wizard"], "once": False}]),
        "advanced",
    )
    do(g, "choose", "start->hall")
    assert g.state.class_pending == ["rogue"]  # unknown classes are left out
    do(g, "choose_class", "rogue")
    # Coming back: the reader already has a class, so nothing is asked.
    g._apply([ChooseClass()], "test")
    assert g.state.class_pending is None
    assert g.state.character_class == "rogue"


def test_choose_class_does_nothing_where_classes_are_picked_at_the_start() -> None:
    g, _ = start(story_book(), "medium")  # medium has no classes
    do(g, "choose", "start->hall")
    assert g.state.class_pending is None
    rules = default_rule_system()  # advanced: picked at the start
    g, _ = start(book_with(rules), "advanced", character_class="rogue")
    g._apply([ChooseClass()], "test")
    assert g.state.class_pending is None
    assert g.state.character_class == "rogue"


def test_choosing_a_class_from_a_choice_and_in_validation() -> None:
    b = story_book(on_hall=[])
    start_node = next(n for n in b.nodes if n.key == "start")
    first = start_node.choices[1]  # into the hall
    b = replace(
        b,
        nodes=tuple(
            replace(
                n,
                choices=(
                    n.choices[0],
                    replace(first, effects=effects({"op": "choose_class", "min_tier": "advanced"})),
                    *n.choices[2:],
                ),
            )
            if n.key == "start"
            else n
            for n in b.nodes
        ),
    )
    g, _ = start(b, "advanced")
    do(g, "choose", first.id)
    assert g.node is not None
    assert g.node.key == "hall"  # the choice still goes where it leads
    assert [a.type for a in g.available()] == ["choose_class"] * 3
    assert not [p for p in validate_book(b) if p.code in ("no_classes", "class_at_start")]

    bad = story_book(on_hall=[{"op": "choose_class", "classes": ["wizard"]}])
    codes = {p.code for p in validate_book(bad)}
    assert {"unknown_class", "no_classes"} <= codes  # and Basic has no classes at all
