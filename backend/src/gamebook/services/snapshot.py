"""Build core snapshots from the database and run validation."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from gamebook.core import model as m
from gamebook.core.analysis import Problem, validate_book
from gamebook.core.effects import Effect
from gamebook.core.rules import RuleSystemDef
from gamebook.db.models import (
    Book,
    Character,
    Choice,
    Encounter,
    Enemy,
    Item,
    LoreEntry,
    Node,
    RandomTable,
    RuleSystem,
)
from gamebook.services import refs
from gamebook.services.common import require

_EFFECTS = TypeAdapter(list[Effect])


def _effects(raw: list[dict[str, Any]]) -> tuple[Effect, ...]:
    try:
        return tuple(_EFFECTS.validate_python(raw))
    except ValidationError:
        return ()


def active_rules(session: Session, series_id: str) -> RuleSystemDef | None:
    row = session.scalar(
        select(RuleSystem).where(RuleSystem.series_id == series_id, RuleSystem.is_active)
    )
    if row is None:
        return None
    try:
        return RuleSystemDef.model_validate(row.definition)
    except ValidationError:
        return None


def load_book_nodes(session: Session, book_id: str) -> list[Node]:
    return list(
        session.scalars(
            select(Node)
            .where(Node.book_id == book_id)
            .options(
                selectinload(Node.variants),
                selectinload(Node.choices).selectinload(Choice.outcomes),
                selectinload(Node.encounters).selectinload(Encounter.enemies),
                selectinload(Node.items),
                selectinload(Node.shop_items),
                selectinload(Node.characters),
            )
            .order_by(Node.key)
        )
    )


def _node(n: Node) -> m.Node:
    return m.Node(
        id=n.id,
        key=n.key,
        title=n.title,
        act_id=n.act_id,
        is_act_entry=n.is_act_entry,
        is_act_exit=n.is_act_exit,
        ending_kind=n.ending_kind,  # type: ignore[arg-type]
        ending_grade=n.ending_grade,  # type: ignore[arg-type]
        on_enter=_effects(n.on_enter),
        variants=tuple(
            m.Variant(id=v.id, label=v.label, condition=v.condition, priority=v.priority)
            for v in n.variants
        ),
        choices=tuple(
            m.Choice(
                id=c.id,
                node_id=n.id,
                label=c.label,
                kind=c.kind,  # type: ignore[arg-type]
                condition=c.condition,
                min_tier=c.min_tier,
                effects=_effects(c.effects),
                dice=c.dice,
                test=c.test,
                encounter_id=c.encounter_id,
                flee_allowed=c.flee_allowed,
                outcomes=tuple(
                    m.Outcome(
                        id=o.id,
                        key=o.key,
                        target_id=o.target_node_id,
                        range_lo=o.range_lo,
                        range_hi=o.range_hi,
                    )
                    for o in c.outcomes
                ),
            )
            for c in n.choices
        ),
        encounters=tuple(
            m.Encounter(
                id=e.id,
                label=e.label,
                mode=e.mode,  # type: ignore[arg-type]
                fight=e.fight,  # type: ignore[arg-type]
                table_id=e.table_id,
                enemies=tuple(
                    m.EncounterEnemy(enemy_id=x.enemy_id, level=x.level, count=x.count)
                    for x in e.enemies
                ),
            )
            for e in n.encounters
        ),
        items=tuple(m.Placement(item_id=p.item_id, qty=p.qty) for p in n.items),
        shop=(
            tuple(
                m.ShopEntry(item_id=s.item_id, price=s.price, stock=s.stock) for s in n.shop_items
            )
            if n.is_shop
            else None
        ),
        section_pin=n.section_pin,
    )


def _table_entry(raw: dict[str, Any]) -> m.TableEntry:
    return m.TableEntry(
        lo=int(raw.get("lo", 0)),
        hi=int(raw.get("hi", 0)),
        kind=raw.get("kind", "nothing"),
        enemies=tuple(
            (str(e["enemy"]), int(e.get("level", 1)), int(e.get("count", 1)))
            for e in raw.get("enemies", [])
        ),
        item=raw.get("item"),
        qty=int(raw.get("qty", 1)),
        amount=raw.get("amount"),
    )


def book_snapshot(session: Session, book_id: str) -> m.BookSnapshot:
    book = require(session, Book, book_id)
    sid = book.series_id

    def scoped(model: type[Any]) -> list[Any]:
        return list(
            session.scalars(select(model).where(model.series_id == sid).order_by(model.key))
        )

    return m.BookSnapshot(
        book_id=book.id,
        series_id=sid,
        title=book.title,
        start_node_id=book.start_node_id,
        acts=tuple(
            m.Act(id=a.id, key=a.key, title=a.title, position=a.position) for a in book.acts
        ),
        nodes=tuple(_node(n) for n in load_book_nodes(session, book_id)),
        rules=active_rules(session, sid),
        items=tuple(
            m.Item(
                id=i.id,
                key=i.key,
                name=i.name,
                book_id=i.book_id,
                category=i.category,
                modifiers=tuple(
                    m.ItemModifier(stat=x["stat"], amount=x["amount"], min_tier=x.get("min_tier"))
                    for x in i.modifiers
                ),
                use_effects=_effects(i.use_effects),
            )
            for i in scoped(Item)
        ),
        enemies=tuple(
            m.Enemy(
                id=e.id,
                key=e.key,
                name=e.name,
                book_id=e.book_id,
                stat_formulas=dict(e.stat_formulas),
                default_level=e.default_level,
            )
            for e in scoped(Enemy)
        ),
        tables=tuple(
            m.RandomTable(
                id=t.id,
                key=t.key,
                name=t.name,
                book_id=t.book_id,
                dice=t.dice,
                entries=tuple(_table_entry(x) for x in t.entries),
            )
            for t in scoped(RandomTable)
        ),
        characters=tuple(
            m.Entity(id=c.id, key=c.key, name=c.name, book_id=c.book_id) for c in scoped(Character)
        ),
        lore=tuple(
            m.Entity(id=x.id, key=x.key, name=x.name, book_id=x.book_id) for x in scoped(LoreEntry)
        ),
        series_flags_set=refs.flags_set_in_series(session, sid),
    )


def problems(session: Session, book_id: str) -> list[Problem]:
    return validate_book(book_snapshot(session, book_id))
