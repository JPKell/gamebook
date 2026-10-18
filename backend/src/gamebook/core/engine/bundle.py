"""BookSnapshot ⇄ plain JSON (the "game bundle", SPEC §3.3 / §6.2).

Used by golden traces now and by the standalone player later. Effects and the
rule system are pydantic models; everything else is frozen dataclasses.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from pydantic import BaseModel, TypeAdapter

from gamebook.core import model as m
from gamebook.core.effects import Effect
from gamebook.core.rules.schema import RuleSystemDef

BUNDLE_FORMAT = "gamebook-bundle"
BUNDLE_VERSION = 1

_EFFECTS = TypeAdapter(list[Effect])


def _plain(value: Any) -> Any:
    if isinstance(value, RuleSystemDef):
        return value.model_dump(mode="json")  # None is meaningful (e.g. min: null)
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _plain(getattr(value, f.name))
            for f in dataclasses.fields(value)
            if not f.name.startswith("_")
        }
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, frozenset | set):
        return sorted(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def to_bundle(book: m.BookSnapshot) -> dict[str, Any]:
    return {"format": BUNDLE_FORMAT, "version": BUNDLE_VERSION, "book": _plain(book)}


def _effects(raw: list[dict[str, Any]]) -> tuple[Effect, ...]:
    return tuple(_EFFECTS.validate_python(raw))


def _node(d: dict[str, Any]) -> m.Node:
    return m.Node(
        id=d["id"],
        key=d["key"],
        title=d["title"],
        act_id=d["act_id"],
        shop_sell_rate=d.get("shop_sell_rate"),
        is_act_entry=d.get("is_act_entry", False),
        is_act_exit=d.get("is_act_exit", False),
        ending_kind=d.get("ending_kind"),
        ending_grade=d.get("ending_grade"),
        on_enter=_effects(d.get("on_enter", [])),
        variants=tuple(m.Variant(**v) for v in d.get("variants", [])),
        choices=tuple(
            m.Choice(
                **{k: v for k, v in c.items() if k not in ("effects", "outcomes")},
                effects=_effects(c.get("effects", [])),
                outcomes=tuple(m.Outcome(**o) for o in c.get("outcomes", [])),
            )
            for c in d.get("choices", [])
        ),
        encounters=tuple(
            m.Encounter(
                **{k: v for k, v in e.items() if k != "enemies"},
                enemies=tuple(m.EncounterEnemy(**x) for x in e.get("enemies", [])),
            )
            for e in d.get("encounters", [])
        ),
        items=tuple(m.Placement(**p) for p in d.get("items", [])),
        shop=tuple(m.ShopEntry(**s) for s in d["shop"]) if d.get("shop") is not None else None,
        section_pin=d.get("section_pin"),
    )


def from_bundle(bundle: dict[str, Any]) -> m.BookSnapshot:
    if bundle.get("format") != BUNDLE_FORMAT:
        raise ValueError("Not a game bundle")
    if int(bundle.get("version", 0)) > BUNDLE_VERSION:
        raise ValueError("Bundle is from a newer version")
    d = bundle["book"]
    return m.BookSnapshot(
        book_id=d["book_id"],
        series_id=d["series_id"],
        title=d["title"],
        start_node_id=d.get("start_node_id"),
        acts=tuple(m.Act(**a) for a in d.get("acts", [])),
        nodes=tuple(_node(n) for n in d.get("nodes", [])),
        rules=RuleSystemDef.model_validate(d["rules"]) if d.get("rules") else None,
        items=tuple(
            m.Item(
                **{k: v for k, v in i.items() if k not in ("modifiers", "use_effects")},
                modifiers=tuple(m.ItemModifier(**x) for x in i.get("modifiers", [])),
                use_effects=_effects(i.get("use_effects", [])),
            )
            for i in d.get("items", [])
        ),
        enemies=tuple(m.Enemy(**e) for e in d.get("enemies", [])),
        tables=tuple(
            m.RandomTable(
                **{k: v for k, v in t.items() if k != "entries"},
                entries=tuple(
                    m.TableEntry(**{**x, "enemies": tuple(tuple(e) for e in x.get("enemies", []))})
                    for x in t.get("entries", [])
                ),
            )
            for t in d.get("tables", [])
        ),
        characters=tuple(m.Entity(**c) for c in d.get("characters", [])),
        lore=tuple(m.Entity(**c) for c in d.get("lore", [])),
        series_flags_set=frozenset(d.get("series_flags_set", [])),
    )
