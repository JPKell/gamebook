"""A small book exercising every engine feature, for tests and golden traces."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from gamebook.core.model import (
    BookSnapshot,
    Choice,
    ChoiceKind,
    Encounter,
    EncounterEnemy,
    Enemy,
    Item,
    ItemModifier,
    Outcome,
    Placement,
    RandomTable,
    ShopEntry,
    TableEntry,
    Variant,
)

from .builders import book, effects, ending, goto, node, with_choices

ITEMS = (
    Item(
        id="i-potion",
        key="potion",
        name="Potion",
        category="consumable",
        use_effects=effects({"op": "modify", "stat": "STAMINA", "amount": "4"}),
    ),
    Item(id="i-rope", key="rope", name="Rope", value=6),
    Item(
        id="i-sword",
        key="sword",
        name="Sword",
        category="equipment",
        slot="weapon",
        value=10,
        modifiers=(ItemModifier(stat="SKILL", amount="2", min_tier="medium"),),
    ),
    Item(id="i-key", key="iron_key", name="Iron Key", category="key"),
)
ENEMIES = (
    Enemy(
        id="e-orc",
        key="orc",
        name="Orc",
        stat_formulas={
            "SKILL": "5 + level",
            "STAMINA": "4 + level * 2",
            "ARMOR": "floor(level / 2)",
        },
    ),
    Enemy(
        id="e-rat",
        key="rat",
        name="Rat",
        stat_formulas={"SKILL": "3", "STAMINA": "2", "ARMOR": "0"},
    ),
    Enemy(
        id="e-wall",
        key="wall",
        name="Living Wall",
        stat_formulas={"SKILL": "0", "STAMINA": "999", "ARMOR": "999"},
    ),
)
TABLES = (
    RandomTable(
        id="t-den",
        key="den",
        name="Den",
        dice="1d6",
        entries=(
            TableEntry(1, 2, "nothing"),
            TableEntry(3, 4, "item", item="potion"),
            TableEntry(5, 6, "enemies", enemies=(("rat", 1, 2),)),
        ),
    ),
)


def choice(
    id_: str,
    src: str,
    kind: ChoiceKind,
    outcomes: dict[str, str | None],
    ranges: dict[str, tuple[int, int]] | None = None,
    **kw: Any,
) -> Choice:
    ranges = ranges or {}
    return Choice(
        id=id_,
        node_id=src,
        label=id_,
        kind=kind,
        outcomes=tuple(
            Outcome(
                id=f"{id_}-{k}",
                key=k,
                target_id=v,
                range_lo=ranges[k][0] if k in ranges else None,
                range_hi=ranges[k][1] if k in ranges else None,
            )
            for k, v in outcomes.items()
        ),
        **kw,
    )


def engine_book() -> BookSnapshot:
    start = replace(
        with_choices(
            node("start"),
            goto("start", "market", "To market"),
            goto("start", "hall", "Into the hall"),
            goto("start", "vault", "Unlock the vault", condition="has(iron_key)"),
            replace(
                goto("start", "secret", "Secret door", condition="flag(NEVER)"),
                unmet_display="show_disabled",
            ),
            goto("start", "elite", "Elite path", min_tier="advanced"),
        ),
        on_enter=effects(
            {"op": "give", "item": "potion", "qty": 2},
            {"op": "set_flag", "flag": "ARRIVED"},
            {"op": "modify", "stat": "GOLD", "amount": "1", "once": False},
        ),
        variants=(
            Variant("start-v", "First"),
            Variant("start-back", "Back again", "visits(start) > 1", priority=1),
        ),
        items=(Placement("i-rope"),),
    )
    market = replace(
        with_choices(node("market"), goto("market", "start", "Leave")),
        shop=(ShopEntry("i-sword", price=8, stock=1), ShopEntry("i-key", price=50)),
        shop_sell_rate=50,
    )
    hall = replace(
        with_choices(
            node("hall"),
            choice(
                "fight",
                "hall",
                "combat",
                {"win": "den", "lose": "dead", "flee": "start"},
                encounter_id="enc-orc",
                flee_allowed=True,
            ),
            choice(
                "gamble",
                "hall",
                "roll",
                {"low": "trap", "high": "den"},
                {"low": (2, 6), "high": (7, 12)},
                dice="2d6",
            ),
            choice("luck", "hall", "test", {"success": "den", "failure": "trap"}, test="luck"),
        ),
        encounters=(
            Encounter("enc-orc", "Orc guard", enemies=(EncounterEnemy("e-orc", level=2),)),
        ),
    )
    den = replace(
        with_choices(
            node("den"),
            choice("rats", "den", "combat", {"win": "end", "lose": "dead"}, encounter_id="enc-den"),
            choice(
                "wall", "den", "combat", {"win": "end", "lose": "dead"}, encounter_id="enc-wall"
            ),
        ),
        encounters=(
            Encounter("enc-den", "Den", mode="table", table_id="t-den"),
            Encounter(
                "enc-wall",
                "Wall",
                fight="simultaneous",
                enemies=(EncounterEnemy("e-wall"), EncounterEnemy("e-rat", count=2)),
            ),
        ),
    )
    trap = replace(
        with_choices(node("trap"), goto("trap", "den", "Crawl on")),
        on_enter=effects({"op": "modify", "stat": "STAMINA", "amount": "-3", "once": False}),
    )
    return book(
        start,
        market,
        hall,
        den,
        trap,
        with_choices(node("vault"), goto("vault", "end", "Take the treasure")),
        with_choices(node("secret"), goto("secret", "end")),
        with_choices(node("elite"), goto("elite", "end")),
        ending("end"),
        ending("dead", kind="death"),
        items=ITEMS,
        enemies=ENEMIES,
        tables=TABLES,
    )
