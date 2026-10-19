"""Node use-cases: nodes, text variants, choices, encounters, placements, shops."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.core.keys import unique_key
from gamebook.core.model import OUTCOME_KEYS, ChoiceKind
from gamebook.db.models import (
    Act,
    Book,
    Character,
    Choice,
    ChoiceOutcome,
    Encounter,
    EncounterEnemy,
    Enemy,
    Item,
    LoreEntry,
    Node,
    NodeCharacter,
    NodeItem,
    RandomTable,
    RefIndex,
    ShopItem,
    TextVariant,
)
from gamebook.schemas.node import (
    ChoiceCreate,
    ChoiceUpdate,
    DuplicateRequest,
    EncounterIn,
    LayoutUpdate,
    NodeCreate,
    NodeUpdate,
    OutcomeIn,
    PlacementIn,
    ShopIn,
    VariantIn,
    VariantUpdate,
)
from gamebook.services import refs
from gamebook.services.common import (
    apply_order,
    assign_key,
    key_follows_title,
    next_position,
    require,
    taken_keys,
)
from gamebook.services.errors import InvalidError
from gamebook.services.refs import dump_effects

# ── helpers ──────────────────────────────────────────────────────────────


def _book_of(session: Session, node: Node) -> Book:
    return require(session, Book, node.book_id)


def _require_in_book(session: Session, node_id: str, book_id: str, field: str) -> Node:
    node = require(session, Node, node_id)
    if node.book_id != book_id:
        raise InvalidError("That node belongs to a different book", field=field)
    return node


def _require_book_entity(
    session: Session,
    model: type[Enemy | Item | RandomTable | Character | LoreEntry],
    id_: str,
    book: Book,
    field: str,
) -> None:
    """The entity must be shared in this book's series, or specific to this book."""
    obj = require(session, model, id_)
    if obj.series_id != book.series_id:
        raise InvalidError(f"That {model.__tablename__} belongs to a different series", field=field)
    if obj.book_id is not None and obj.book_id != book.id:
        raise InvalidError(f"That {model.__tablename__} belongs to a different book", field=field)


def default_outcomes(kind: ChoiceKind, flee_allowed: bool = False) -> list[OutcomeIn]:
    if kind == "roll":
        return [
            OutcomeIn(key="low", range_lo=2, range_hi=6),
            OutcomeIn(key="high", range_lo=7, range_hi=12),
        ]
    keys = list(OUTCOME_KEYS[kind])
    if kind == "combat" and not flee_allowed:
        keys.remove("flee")
    return [OutcomeIn(key=k) for k in keys]


def _reindex_targeting_nodes(session: Session, book: Book, keys: Sequence[str]) -> None:
    """Refresh refs of choices that point at (now changed/deleted) nodes."""
    if not keys:
        return
    sources = session.execute(
        select(RefIndex.source_type, RefIndex.source_id)
        .where(
            RefIndex.book_id == book.id,
            RefIndex.target_type == "node",
            RefIndex.target_key.in_(list(keys)),
        )
        .distinct()
    ).all()
    ctx = refs.RefContext(session, book.series_id)
    for source_type, source_id in sources:
        model = {"choice": Choice, "variant": TextVariant, "node": Node}.get(source_type)
        obj = session.get(model, source_id) if model else None
        if obj is not None:
            session.refresh(obj)
            refs.reindex(session, cast(refs.SourceType, source_type), obj, ctx)


# ── nodes ────────────────────────────────────────────────────────────────


def create_node(session: Session, book_id: str, data: NodeCreate) -> Node:
    book = require(session, Book, book_id)
    act = require(session, Act, data.act_id)
    if act.book_id != book_id:
        raise InvalidError("That act belongs to a different book", field="act_id")
    node = Node(
        book_id=book_id,
        act_id=act.id,
        key=assign_key(session, Node, data.key, data.title, book_id=book_id),
        title=data.title,
        beat_notes=data.beat_notes,
        x=data.x,
        y=data.y,
    )
    node.variants.append(TextVariant(label="Default", position=0))
    session.add(node)
    session.flush()
    if book.start_node_id is None:
        book.start_node_id = node.id
    refs.reindex_node_tree(session, node)
    # visits(<key>) written before this node existed can now resolve.
    _reindex_targeting_nodes(session, book, [node.key])
    if data.link_from is not None:
        _require_in_book(session, data.link_from.node_id, book_id, "link_from.node_id")
        create_choice(
            session,
            data.link_from.node_id,
            ChoiceCreate(label=data.link_from.label, target_node_id=node.id),
        )
    session.flush()
    return node


def update_node(session: Session, node_id: str, data: NodeUpdate) -> Node:
    node = require(session, Node, node_id)
    book = _book_of(session, node)
    changes = data.model_dump(exclude_unset=True)
    old_key = node.key

    title = changes.get("title")
    if (
        title is not None
        and title != node.title
        and changes.get("key") is None
        and key_follows_title(node.key, node.title, "node")
    ):
        node.key = assign_key(session, Node, None, title, exclude_id=node.id, book_id=node.book_id)
    if changes.get("key") is not None:
        node.key = assign_key(
            session, Node, data.key, node.title, exclude_id=node.id, book_id=node.book_id
        )
    if data.act_id is not None:
        act = require(session, Act, data.act_id)
        if act.book_id != node.book_id:
            raise InvalidError("That act belongs to a different book", field="act_id")
        node.act_id = act.id
    if "location_id" in changes:
        if data.location_id is not None:
            _require_book_entity(session, LoreEntry, data.location_id, book, "location_id")
        node.location_id = data.location_id
    if "canonical_predecessor_id" in changes:
        if data.canonical_predecessor_id is not None:
            _require_in_book(
                session, data.canonical_predecessor_id, node.book_id, "canonical_predecessor_id"
            )
        node.canonical_predecessor_id = data.canonical_predecessor_id
    if data.character_ids is not None:
        for cid in data.character_ids:
            _require_book_entity(session, Character, cid, book, "character_ids")
        node.characters = [
            NodeCharacter(character_id=cid) for cid in dict.fromkeys(data.character_ids)
        ]
    if data.on_enter is not None:
        node.on_enter = dump_effects(data.on_enter)
    nullable = ("ending_kind", "ending_grade", "section_pin")
    for field in (
        "title",
        "beat_notes",
        "summary",
        "is_act_entry",
        "is_act_exit",
        "ending_kind",
        "ending_grade",
        "ending_label",
        "section_pin",
        "x",
        "y",
        "collapsed",
    ):
        if field in changes and (changes[field] is not None or field in nullable):
            setattr(node, field, changes[field])
    if data.ending_kind is None and "ending_kind" in changes:
        node.ending_grade = None
    if data.style_override is not None:
        node.style_override = dict(data.style_override)
    session.flush()

    if node.key != old_key:
        refs.rename_key(session, book.series_id, "node", old_key, node.key, book_id=book.id)
        _reindex_targeting_nodes(session, book, [node.key])
    refs.reindex(session, "node", node)
    return node


def delete_nodes(session: Session, book: Book, nodes: Sequence[Node]) -> None:
    if not nodes:
        return
    keys = [n.key for n in nodes]
    ids = {n.id for n in nodes}
    for n in nodes:
        refs.drop_node_tree(session, n)
    if book.start_node_id in ids:
        book.start_node_id = None
    session.flush()
    for n in nodes:
        session.delete(n)
    session.flush()
    session.expire_all()
    _reindex_targeting_nodes(session, book, keys)


def delete_node(session: Session, node_id: str) -> None:
    node = require(session, Node, node_id)
    delete_nodes(session, _book_of(session, node), [node])


def save_layout(session: Session, book_id: str, data: LayoutUpdate) -> None:
    require(session, Book, book_id)
    ids = [p.id for p in data.positions]
    nodes = {
        n.id: n
        for n in session.scalars(select(Node).where(Node.book_id == book_id, Node.id.in_(ids)))
    }
    missing = set(ids) - set(nodes)
    if missing:
        raise InvalidError(f"{len(missing)} node(s) are not in this book", node_ids=sorted(missing))
    for p in data.positions:
        nodes[p.id].x = p.x
        nodes[p.id].y = p.y
    session.flush()


def duplicate_nodes(session: Session, book_id: str, data: DuplicateRequest) -> dict[str, str]:
    """Copy nodes; links between copied nodes are remapped onto the copies."""
    book = require(session, Book, book_id)
    originals = [
        _require_in_book(session, i, book_id, "node_ids") for i in dict.fromkeys(data.node_ids)
    ]
    taken = taken_keys(session, Node, book_id=book_id)
    mapping: dict[str, str] = {}
    copies: list[tuple[Node, Node]] = []
    for src in originals:
        key = unique_key(f"{src.key[:58]}_copy", taken)
        taken.add(key)
        dup = Node(
            book_id=book_id,
            act_id=src.act_id,
            key=key,
            title=f"{src.title} (copy)"[:200],
            beat_notes=src.beat_notes,
            summary=src.summary,
            is_act_entry=src.is_act_entry,
            is_act_exit=src.is_act_exit,
            ending_kind=src.ending_kind,
            ending_grade=src.ending_grade,
            ending_label=src.ending_label,
            location_id=src.location_id,
            style_override=dict(src.style_override),
            on_enter=list(src.on_enter),
            is_shop=src.is_shop,
            shop_sell_rate=src.shop_sell_rate,
            x=src.x + data.offset_x,
            y=src.y + data.offset_y,
        )
        dup.variants = [
            TextVariant(
                label=v.label, condition=v.condition, priority=v.priority, position=v.position
            )
            for v in src.variants
        ]
        dup.items = [NodeItem(item_id=p.item_id, qty=p.qty, position=p.position) for p in src.items]
        dup.shop_items = [
            ShopItem(item_id=s.item_id, price=s.price, stock=s.stock, position=s.position)
            for s in src.shop_items
        ]
        dup.characters = [NodeCharacter(character_id=c.character_id) for c in src.characters]
        session.add(dup)
        session.flush()
        mapping[src.id] = dup.id
        copies.append((src, dup))

    for src, dup in copies:
        enc_map: dict[str, str] = {}
        for e in src.encounters:
            new_e = Encounter(
                node_id=dup.id,
                label=e.label,
                mode=e.mode,
                fight=e.fight,
                table_id=e.table_id,
                position=e.position,
            )
            new_e.enemies = [
                EncounterEnemy(
                    enemy_id=x.enemy_id, level=x.level, count=x.count, position=x.position
                )
                for x in e.enemies
            ]
            session.add(new_e)
            session.flush()
            enc_map[e.id] = new_e.id
        for c in src.choices:
            new_c = Choice(
                node_id=dup.id,
                position=c.position,
                label=c.label,
                kind=c.kind,
                condition=c.condition,
                unmet_display=c.unmet_display,
                print_text=c.print_text,
                min_tier=c.min_tier,
                effects=list(c.effects),
                dice=c.dice,
                test=c.test,
                encounter_id=enc_map.get(c.encounter_id) if c.encounter_id else None,
                flee_allowed=c.flee_allowed,
            )
            new_c.outcomes = [
                ChoiceOutcome(
                    key=o.key,
                    position=o.position,
                    range_lo=o.range_lo,
                    range_hi=o.range_hi,
                    target_node_id=mapping.get(o.target_node_id, o.target_node_id)
                    if o.target_node_id
                    else None,
                )
                for o in c.outcomes
            ]
            session.add(new_c)
        session.flush()
        session.refresh(dup)
        refs.reindex_node_tree(session, dup, refs.RefContext(session, book.series_id))
    return mapping


# ── variants ─────────────────────────────────────────────────────────────


def create_variant(session: Session, node_id: str, data: VariantIn) -> TextVariant:
    require(session, Node, node_id)
    v = TextVariant(
        node_id=node_id,
        position=next_position(session, TextVariant.position, node_id=node_id),
        label=data.label,
        condition=data.condition or None,
        priority=data.priority,
    )
    session.add(v)
    session.flush()
    refs.reindex(session, "variant", v)
    return v


def update_variant(session: Session, variant_id: str, data: VariantUpdate) -> TextVariant:
    v = require(session, TextVariant, variant_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("label") is not None:
        v.label = changes["label"]
    if "condition" in changes:
        v.condition = data.condition or None
    if changes.get("priority") is not None:
        v.priority = changes["priority"]
    session.flush()
    refs.reindex(session, "variant", v)
    return v


def delete_variant(session: Session, variant_id: str) -> None:
    v = require(session, TextVariant, variant_id)
    refs.drop(session, "variant", [v.id])
    refs.drop_placements(session, "variant_id", [v.id])  # its art goes with it (FK cascade)
    session.delete(v)
    session.flush()


def reorder_variants(session: Session, node_id: str, ids: list[str]) -> list[TextVariant]:
    node = require(session, Node, node_id)
    apply_order(list(node.variants), ids)
    session.flush()
    return sorted(node.variants, key=lambda v: v.position)


# ── choices ──────────────────────────────────────────────────────────────


def _set_outcomes(
    session: Session, choice: Choice, outcomes: list[OutcomeIn], book_id: str
) -> None:
    keys = [o.key for o in outcomes]
    if len(set(keys)) != len(keys):
        raise InvalidError("Outcome keys must be unique", field="outcomes")
    for o in outcomes:
        if o.target_node_id is not None:
            _require_in_book(session, o.target_node_id, book_id, "outcomes")
    existing = {o.key: o for o in choice.outcomes}
    new: list[ChoiceOutcome] = []
    for pos, o in enumerate(outcomes):
        row = existing.get(o.key) or ChoiceOutcome(key=o.key)
        row.position = pos
        row.target_node_id = o.target_node_id
        row.range_lo = o.range_lo
        row.range_hi = o.range_hi
        new.append(row)
    choice.outcomes = new


def create_choice(session: Session, node_id: str, data: ChoiceCreate) -> Choice:
    node = require(session, Node, node_id)
    if data.encounter_id is not None and data.encounter_id not in {e.id for e in node.encounters}:
        raise InvalidError("Combat must use one of this node's encounters", field="encounter_id")
    if data.outcomes is not None:
        outcomes = data.outcomes
    else:
        outcomes = default_outcomes(data.kind, data.flee_allowed)
        if data.target_node_id is not None:
            if data.kind != "goto":
                raise InvalidError(
                    "target_node_id is only for goto choices", field="target_node_id"
                )
            outcomes = [OutcomeIn(key="default", target_node_id=data.target_node_id)]
    choice = Choice(
        node_id=node_id,
        position=next_position(session, Choice.position, node_id=node_id),
        label=data.label,
        kind=data.kind,
        condition=data.condition or None,
        unmet_display=data.unmet_display,
        print_text=data.print_text,
        min_tier=data.min_tier,
        effects=dump_effects(data.effects),
        dice=data.dice or ("2d6" if data.kind == "roll" else None),
        test=data.test,
        encounter_id=data.encounter_id,
        flee_allowed=data.flee_allowed,
    )
    session.add(choice)
    session.flush()
    _set_outcomes(session, choice, outcomes, node.book_id)
    session.flush()
    refs.reindex(session, "choice", choice)
    return choice


def update_choice(session: Session, choice_id: str, data: ChoiceUpdate) -> Choice:
    choice = require(session, Choice, choice_id)
    node = require(session, Node, choice.node_id)
    changes = data.model_dump(exclude_unset=True)

    for field in ("label", "unmet_display", "flee_allowed"):
        if changes.get(field) is not None:
            setattr(choice, field, changes[field])
    for field in ("print_text", "min_tier", "dice", "test"):
        if field in changes:
            setattr(choice, field, changes[field] or None)
    if "condition" in changes:
        choice.condition = data.condition or None
    if data.effects is not None:
        choice.effects = dump_effects(data.effects)
    if "encounter_id" in changes:
        if data.encounter_id is not None and data.encounter_id not in {
            e.id for e in node.encounters
        }:
            raise InvalidError(
                "Combat must use one of this node's encounters", field="encounter_id"
            )
        choice.encounter_id = data.encounter_id

    kind_changed = data.kind is not None and data.kind != choice.kind
    if data.kind is not None:
        choice.kind = data.kind
        if choice.kind == "roll" and not choice.dice:
            choice.dice = "2d6"
    if data.outcomes is not None:
        _set_outcomes(session, choice, data.outcomes, node.book_id)
    elif data.target_node_id is not None or "target_node_id" in changes:
        if choice.kind != "goto":
            raise InvalidError("target_node_id is only for goto choices", field="target_node_id")
        _set_outcomes(
            session,
            choice,
            [OutcomeIn(key="default", target_node_id=data.target_node_id)],
            node.book_id,
        )
    elif kind_changed or (data.flee_allowed is not None and choice.kind == "combat"):
        # Keep destinations for outcome keys the new kind shares.
        current = {o.key: o.target_node_id for o in choice.outcomes}
        if choice.kind == "goto" and "default" not in current and current:
            current["default"] = next(iter(current.values()))
        outcomes = [
            OutcomeIn(
                key=o.key,
                target_node_id=current.get(o.key),
                range_lo=o.range_lo,
                range_hi=o.range_hi,
            )
            for o in default_outcomes(cast(ChoiceKind, choice.kind), choice.flee_allowed)
        ]
        _set_outcomes(session, choice, outcomes, node.book_id)
    session.flush()
    refs.reindex(session, "choice", choice)
    return choice


def delete_choice(session: Session, choice_id: str) -> None:
    choice = require(session, Choice, choice_id)
    refs.drop(session, "choice", [choice.id])
    session.delete(choice)
    session.flush()


def reorder_choices(session: Session, node_id: str, ids: list[str]) -> list[Choice]:
    node = require(session, Node, node_id)
    apply_order(list(node.choices), ids)
    session.flush()
    return sorted(node.choices, key=lambda c: c.position)


# ── encounters ───────────────────────────────────────────────────────────


def _apply_encounter(session: Session, enc: Encounter, data: EncounterIn, book: Book) -> None:
    for e in data.enemies:
        _require_book_entity(session, Enemy, e.enemy_id, book, "enemies")
    if data.table_id is not None:
        _require_book_entity(session, RandomTable, data.table_id, book, "table_id")
    enc.label = data.label
    enc.mode = data.mode
    enc.fight = data.fight
    enc.table_id = data.table_id
    enc.enemies = [
        EncounterEnemy(enemy_id=e.enemy_id, level=e.level, count=e.count, position=i)
        for i, e in enumerate(data.enemies)
    ]


def create_encounter(session: Session, node_id: str, data: EncounterIn) -> Encounter:
    node = require(session, Node, node_id)
    enc = Encounter(
        node_id=node_id, position=next_position(session, Encounter.position, node_id=node_id)
    )
    _apply_encounter(session, enc, data, _book_of(session, node))
    session.add(enc)
    session.flush()
    refs.reindex(session, "encounter", enc)
    return enc


def update_encounter(session: Session, encounter_id: str, data: EncounterIn) -> Encounter:
    enc = require(session, Encounter, encounter_id)
    node = require(session, Node, enc.node_id)
    _apply_encounter(session, enc, data, _book_of(session, node))
    session.flush()
    refs.reindex(session, "encounter", enc)
    return enc


def delete_encounter(session: Session, encounter_id: str) -> None:
    enc = require(session, Encounter, encounter_id)
    refs.drop(session, "encounter", [enc.id])
    session.delete(enc)
    session.flush()


# ── placements & shop ────────────────────────────────────────────────────


def set_placements(session: Session, node_id: str, items: list[PlacementIn]) -> Node:
    node = require(session, Node, node_id)
    book = _book_of(session, node)
    for p in items:
        _require_book_entity(session, Item, p.item_id, book, "items")
    node.items = [NodeItem(item_id=p.item_id, qty=p.qty, position=i) for i, p in enumerate(items)]
    session.flush()
    refs.reindex(session, "node", node)
    return node


def set_shop(session: Session, node_id: str, data: ShopIn) -> Node:
    node = require(session, Node, node_id)
    book = _book_of(session, node)
    for s in data.items:
        _require_book_entity(session, Item, s.item_id, book, "items")
    node.is_shop = data.is_shop
    node.shop_sell_rate = data.sell_rate if data.is_shop else None
    node.shop_items = (
        [
            ShopItem(item_id=s.item_id, price=s.price, stock=s.stock, position=i)
            for i, s in enumerate(data.items)
        ]
        if data.is_shop
        else []
    )
    session.flush()
    refs.reindex(session, "node", node)
    return node
