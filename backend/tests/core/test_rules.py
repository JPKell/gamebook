import pytest

from gamebook.core.analysis import validate_rule_system
from gamebook.core.rules import (
    CombatDef,
    RuleSystemDef,
    StatDef,
    TierDef,
    TierError,
    default_rule_system,
    effective_tier,
    tier_chain,
)


def test_default_rule_system_is_valid() -> None:
    assert validate_rule_system(default_rule_system()) == []


def test_tier_inheritance_merges() -> None:
    rules = default_rule_system()
    basic = effective_tier(rules, "basic")
    medium = effective_tier(rules, "medium")
    advanced = effective_tier(rules, "advanced")

    assert set(basic.stats) == {"SKILL", "STAMINA", "LUCK", "GOLD"}
    assert set(medium.stats) == set(basic.stats) | {"ARMOR", "XP", "LEVEL"}
    assert medium.stat_origin["SKILL"] == "basic"
    assert medium.stat_origin["ARMOR"] == "medium"
    assert basic.enemy_stats() == {"SKILL", "STAMINA"}
    assert "LUCK" not in medium.enemy_stats()

    # Combat: scalars inherited, hooks accumulate in order.
    assert advanced.combat.player_attack == "2d6 + player.SKILL"
    assert advanced.combat.damage_hooks == [
        "max(1, damage - target.ARMOR)",
        "natural == 12 ? damage * 2 : damage",
    ]
    assert basic.combat.damage_hooks == []
    assert advanced.slots == ("weapon", "body", "shield")
    assert set(advanced.skills) == {"TRACKING", "ARCHERY", "STEALTH", "LORE"}
    assert basic.skills == {}
    assert [advanced.index, medium.index, basic.index] == [2, 1, 0]


def test_child_overrides_stat_definition() -> None:
    rules = RuleSystemDef(
        tiers=[
            TierDef(key="a", label="A", stats=[StatDef(key="HP", label="HP", initial="10")]),
            TierDef(
                key="b",
                label="B",
                parent="a",
                stats=[StatDef(key="HP", label="Hit Points", initial="20")],
            ),
        ]
    )
    assert effective_tier(rules, "b").stats["HP"].initial == "20"
    assert effective_tier(rules, "b").stat_origin["HP"] == "a"


def test_bad_chains() -> None:
    cyclic = RuleSystemDef(
        tiers=[TierDef(key="a", label="A", parent="b"), TierDef(key="b", label="B", parent="a")]
    )
    with pytest.raises(TierError, match="cyclic"):
        tier_chain(cyclic, "a")
    orphan = RuleSystemDef(tiers=[TierDef(key="a", label="A", parent="zzz")])
    with pytest.raises(TierError, match="unknown parent"):
        tier_chain(orphan, "a")
    codes = {p.code for p in validate_rule_system(cyclic)}
    assert "tier_chain" in codes


def test_rule_system_problems() -> None:
    rules = default_rule_system()
    basic = rules.tiers[0]
    basic.combat = CombatDef(player_attack="2d6 + player.SKIL", damage_stat="LUCK")
    basic.stats.append(StatDef(key="SKILL", label="dup"))
    rules.tiers[2].classes[0].skills.append("FLYING")
    codes = [p.code for p in validate_rule_system(rules)]
    assert "gbx.stat" in codes
    assert "combat_stat" in codes  # LUCK isn't an enemy stat
    assert "duplicate_stat" in codes
    assert "unknown_skill" in codes


def test_tier_order_must_follow_parent() -> None:
    rules = RuleSystemDef(
        tiers=[TierDef(key="b", label="B", parent="a"), TierDef(key="a", label="A")]
    )
    assert "tier_order" in {p.code for p in validate_rule_system(rules)}
