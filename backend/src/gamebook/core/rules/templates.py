"""Starter rule system seeded into new series.

Basic is classic Fighting-Fantasy-style (SKILL/STAMINA/LUCK, 2d6 attack
strength, 2 damage). Medium adds armour and equipment slots. Advanced adds
classes, skills and critical hits. Authors reshape it in the Mechanics designer.
"""

from gamebook.core.rules.schema import (
    ClassDef,
    CombatDef,
    RuleSystemDef,
    SkillDef,
    StatDef,
    TestDef,
    TierDef,
)


def default_rule_system() -> RuleSystemDef:
    return RuleSystemDef(
        tiers=[
            TierDef(
                key="basic",
                label="Basic",
                description="Three stats, two dice, simple combat.",
                rules_text=(
                    "Roll one die and add 6 for your SKILL, two dice and add 12 for your "
                    "STAMINA, and one die plus 6 for your LUCK. You start with 10 Gold.\n\n"
                    "**Fighting.** Each round, roll two dice and add your SKILL; then roll two "
                    "dice and add your opponent's SKILL. Whoever scores higher wounds the "
                    "other for 2 STAMINA. A tie means you both miss. Anyone reduced to 0 "
                    "STAMINA is defeated.\n\n"
                    "**Testing your Luck.** Roll two dice. If the total is equal to or less "
                    "than your LUCK you are lucky. Either way, subtract 1 from your LUCK."
                ),
                stats=[
                    StatDef(
                        key="SKILL",
                        label="Skill",
                        applies_to=["player", "enemy"],
                        initial="1d6 + 6",
                        max_is_initial=True,
                    ),
                    StatDef(
                        key="STAMINA",
                        label="Stamina",
                        applies_to=["player", "enemy"],
                        initial="2d6 + 12",
                        max_is_initial=True,
                        defeat_at=0,
                    ),
                    StatDef(key="LUCK", label="Luck", initial="1d6 + 6", max_is_initial=True),
                    StatDef(key="GOLD", label="Gold", kind="resource", initial="10"),
                ],
                tests=[
                    TestDef.model_validate(
                        {
                            "key": "luck",
                            "label": "Test your Luck",
                            "roll": "2d6",
                            "success": "roll <= player.LUCK",
                            "after": [{"op": "modify", "stat": "LUCK", "amount": "-1"}],
                        }
                    ),
                    TestDef(
                        key="skill",
                        label="Test your Skill",
                        roll="2d6",
                        success="roll <= player.SKILL",
                    ),
                ],
                combat=CombatDef.model_validate(
                    {
                        "player_attack": "2d6 + player.SKILL",
                        "enemy_attack": "2d6 + enemy.SKILL",
                        "damage": "2",
                        "damage_stat": "STAMINA",
                        "multi_enemy": "sequential",
                        "flee_allowed": True,
                        "flee_cost": [{"op": "modify", "stat": "STAMINA", "amount": "-2"}],
                    }
                ),
            ),
            TierDef(
                key="medium",
                label="Medium",
                parent="basic",
                description="Adds armour and equipment slots.",
                rules_text=(
                    "**Armour.** Every wound is reduced by the target's ARMOUR, but always does "
                    "at least 1 damage. You may wear one weapon, one suit of body armour and "
                    "one shield; their bonuses count only while equipped."
                ),
                stats=[StatDef(key="ARMOR", label="Armour", applies_to=["player", "enemy"])],
                slots=["weapon", "body", "shield"],
                combat=CombatDef(damage_hooks=["max(1, damage - target.ARMOR)"]),
            ),
            TierDef(
                key="advanced",
                label="Advanced",
                parent="medium",
                description="Adds classes, skills and critical hits.",
                rules_text=(
                    "**Your calling.** Choose a class: it grants your starting skills, which "
                    "open choices other adventurers cannot take.\n\n"
                    "**Critical hits.** When an attack roll shows double six (a natural 12), "
                    "its damage is doubled."
                ),
                skills=[
                    SkillDef(key="TRACKING", label="Tracking"),
                    SkillDef(key="ARCHERY", label="Archery"),
                    SkillDef(key="STEALTH", label="Stealth"),
                    SkillDef(key="LORE", label="Lore"),
                ],
                classes=[
                    ClassDef(key="ranger", label="Ranger", skills=["TRACKING", "ARCHERY"]),
                    ClassDef(key="rogue", label="Rogue", skills=["STEALTH"]),
                    ClassDef(key="scholar", label="Scholar", skills=["LORE"]),
                ],
                combat=CombatDef(damage_hooks=["natural == 12 ? damage * 2 : damage"]),
            ),
        ]
    )
