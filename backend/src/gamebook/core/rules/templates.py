"""Starter rule system seeded into new series.

Basic is classic Fighting-Fantasy-style (SKILL/STAMINA/LUCK, 2d6 attack
strength, 2 damage). Medium adds armour, equipment slots, experience and
levels. Advanced adds classes (with stat bonuses), skills and critical hits. Authors reshape it in the Mechanics designer.
"""

from gamebook.core.rules.schema import (
    ClassDef,
    CombatDef,
    ProgressionDef,
    RuleSystemDef,
    SkillDef,
    StatBonus,
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
                description="Adds armour, equipment slots, experience and levels.",
                rules_text=(
                    "**Armour.** Every wound is reduced by the target's ARMOUR, but always does "
                    "at least 1 damage. You may wear one weapon, one suit of body armour and "
                    "one shield; their bonuses count only while equipped.\n\n"
                    "**Experience.** You begin at LEVEL 1 with 0 XP. Each enemy you defeat in "
                    "a fight you win earns 10 XP, plus 5 for every level it is above yours "
                    "(or minus 5 for every level below; always at least 1). When your XP "
                    "reaches 100 times your LEVEL, subtract that much XP and go up a level: "
                    "add 2 to your STAMINA and its starting value, and at every third level "
                    "add 1 to your SKILL and its starting value. The highest level is 10."
                ),
                stats=[
                    StatDef(key="ARMOR", label="Armour", applies_to=["player", "enemy"]),
                    StatDef(key="XP", label="Experience", initial="0"),
                    StatDef(key="LEVEL", label="Level", initial="1", min=1),
                ],
                slots=["weapon", "body", "shield"],
                combat=CombatDef(damage_hooks=["max(1, damage - target.ARMOR)"]),
                progression=ProgressionDef(
                    xp_stat="XP",
                    level_stat="LEVEL",
                    xp_award="max(1, 10 + 5 * (enemy_level - level))",
                    xp_to_next="100 * level",
                    max_level=10,
                    level_up=[
                        StatBonus(stat="STAMINA", amount="2"),
                        StatBonus(stat="SKILL", amount="level % 3 == 0 ? 1 : 0"),
                    ],
                ),
            ),
            TierDef(
                key="advanced",
                label="Advanced",
                parent="medium",
                description="Adds classes, skills and critical hits.",
                rules_text=(
                    "**Your calling.** Choose a class: it grants your starting skills, which "
                    "open choices other adventurers cannot take, and a bonus to your stats: "
                    "a Ranger adds 1 to SKILL, a Rogue adds 2 to LUCK and a Scholar adds "
                    "1 to LUCK and 2 to STAMINA.\n\n"
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
                    ClassDef(
                        key="ranger",
                        label="Ranger",
                        skills=["TRACKING", "ARCHERY"],
                        modifiers=[StatBonus(stat="SKILL", amount="1")],
                    ),
                    ClassDef(
                        key="rogue",
                        label="Rogue",
                        skills=["STEALTH"],
                        modifiers=[StatBonus(stat="LUCK", amount="2")],
                    ),
                    ClassDef(
                        key="scholar",
                        label="Scholar",
                        skills=["LORE"],
                        modifiers=[
                            StatBonus(stat="LUCK", amount="1"),
                            StatBonus(stat="STAMINA", amount="2"),
                        ],
                    ),
                ],
                combat=CombatDef(damage_hooks=["natural == 12 ? damage * 2 : damage"]),
            ),
        ]
    )
