"""Tiny builders for BookSnapshot fixtures."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from pydantic import TypeAdapter

from gamebook.core.effects import Effect
from gamebook.core.model import (
    Act,
    BookSnapshot,
    Choice,
    Enemy,
    Item,
    Node,
    Outcome,
    Variant,
)
from gamebook.core.rules import default_rule_system

_effects = TypeAdapter(list[Effect])


def effects(*raw: dict[str, Any]) -> tuple[Effect, ...]:
    return tuple(_effects.validate_python(list(raw)))


def node(key: str, act: str = "act1", **kw: Any) -> Node:
    kw.setdefault("variants", (Variant(id=f"{key}-v", label="Default"),))
    return Node(id=key, key=key, title=key.title(), act_id=act, **kw)


def goto(src: str, target: str | None, label: str = "", **kw: Any) -> Choice:
    return Choice(
        id=f"{src}->{target}",
        node_id=src,
        label=label or f"Go to {target}",
        outcomes=(Outcome(id=f"{src}->{target}-o", key="default", target_id=target),),
        **kw,
    )


def with_choices(n: Node, *choices: Choice) -> Node:
    return replace(n, choices=tuple(choices))


ENEMY_FORMULAS = {"SKILL": "6 + level", "STAMINA": "4 + level * 2", "ARMOR": "floor(level / 3)"}


def book(*nodes: Node, acts: int = 1, start: str | None = "start", **kw: Any) -> BookSnapshot:
    kw.setdefault("rules", default_rule_system())
    kw.setdefault(
        "items",
        (
            Item(id="i-rope", key="rope", name="Rope"),
            Item(id="i-potion", key="potion", name="Potion"),
        ),
    )
    kw.setdefault(
        "enemies", (Enemy(id="e-orc", key="orc", name="Orc", stat_formulas=dict(ENEMY_FORMULAS)),)
    )
    return BookSnapshot(
        book_id="b1",
        series_id="s1",
        title="Test",
        start_node_id=start,
        acts=tuple(
            Act(id=f"act{i}", key=f"act{i}", title=f"Act {i}", position=i)
            for i in range(1, acts + 1)
        ),
        nodes=nodes,
        **kw,
    )


def ending(key: str, act: str = "act1", kind: str = "victory") -> Node:
    return node(key, act, ending_kind=kind)
