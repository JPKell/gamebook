"""RefIndex maintenance, where-used queries and key renames.

Every write that can change references calls ``reindex(...)`` for the affected
source. ``rebuild_series`` recomputes everything and is used after imports and
as the oracle in tests (incremental == full rebuild).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from gamebook.core import gbx
from gamebook.core.effects import Effect, effect_refs, rename_in_effect
from gamebook.core.gbx.scope import Context, RefKind, Scope, ScopeInputs, scope_for
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
    RefIndex,
    RuleSystem,
    TextVariant,
)

SourceType = Literal[
    "node", "choice", "variant", "encounter", "enemy", "item", "table", "character"
]

_EFFECTS = TypeAdapter(list[Effect])


def dump_effects(effects: Sequence[Effect]) -> list[dict[str, Any]]:
    """Canonical JSON storage for effects (defaults omitted)."""
    return [e.model_dump(exclude_none=True, exclude_defaults=False) for e in effects]


_ENTITY_MODELS: dict[str, type[Any]] = {
    "item": Item,
    "enemy": Enemy,
    "table": RandomTable,
    "character": Character,
    "lore": LoreEntry,
}


@dataclass(frozen=True)
class RefRow:
    target_type: str
    target_key: str
    role: str
    field: str = ""
    qty: int | None = None


# ── context ──────────────────────────────────────────────────────────────


class RefContext:
    """Per-series lookups for extraction (tiers, key↔id maps), cached."""

    def __init__(self, session: Session, series_id: str) -> None:
        self.session = session
        self.series_id = series_id
        rules = session.scalar(
            select(RuleSystem).where(RuleSystem.series_id == series_id, RuleSystem.is_active)
        )
        tiers: tuple[str, ...] = ()
        if rules is not None:
            try:
                tiers = RuleSystemDef.model_validate(rules.definition).tier_keys()
            except ValidationError:
                tiers = ()
        self.tiers = tiers
        self._scopes: dict[Context, Scope] = {}
        self._entity_keys: dict[str, dict[str, str]] = {}
        self._node_keys: dict[str, str] = {}

    def scope(self, context: Context) -> Scope:
        if context not in self._scopes:
            self._scopes[context] = scope_for(context, ScopeInputs(tiers=self.tiers))
        return self._scopes[context]

    def entity_key(self, kind: str, id_: str) -> str | None:
        """id → key for item/enemy/table/character/lore."""
        if kind not in self._entity_keys:
            model = _ENTITY_MODELS[kind]
            rows = self.session.execute(
                select(model.id, model.key).where(model.series_id == self.series_id)
            )
            self._entity_keys[kind] = {str(i): str(k) for i, k in rows}
        return self._entity_keys[kind].get(id_)

    def node_key(self, node_id: str) -> str | None:
        if node_id not in self._node_keys:
            key = self.session.scalar(select(Node.key).where(Node.id == node_id))
            if key is None:
                return None
            self._node_keys[node_id] = key
        return self._node_keys[node_id]


# ── extraction ───────────────────────────────────────────────────────────


def _expr_rows(src: str | None, scope: Scope, role: str, field: str) -> list[RefRow]:
    if not src:
        return []
    try:
        expr = gbx.parse(src)
    except gbx.GbxSyntaxError:
        return []
    return [RefRow(r.kind.value, r.key, role, field) for r in gbx.references(expr, scope)]


def _effect_rows(raw: Sequence[dict[str, Any]], ctx: RefContext, field: str) -> list[RefRow]:
    try:
        effects = _EFFECTS.validate_python(list(raw))
    except ValidationError:
        return []
    scope = ctx.scope(Context.AMOUNT)
    rows: list[RefRow] = []
    for i, eff in enumerate(effects):
        qty = getattr(eff, "qty", None) if eff.op in ("give", "take") else None
        for kind, key, role in effect_refs(eff, scope):
            rows.append(
                RefRow(
                    kind.value, key, role, f"{field}[{i}]", qty if kind == RefKind.ITEM else None
                )
            )
    return rows


def extract(source_type: SourceType, obj: Any, ctx: RefContext) -> list[RefRow]:
    rows: list[RefRow] = []
    match source_type:
        case "node":
            n: Node = obj
            rows += _effect_rows(n.on_enter, ctx, "on_enter")
            for p in n.items:
                key = ctx.entity_key("item", p.item_id)
                if key:
                    rows.append(RefRow("item", key, "placement", "items", p.qty))
            for s in n.shop_items:
                key = ctx.entity_key("item", s.item_id)
                if key:
                    rows.append(RefRow("item", key, "shop", "shop_items", s.stock))
            for nc in n.characters:
                key = ctx.entity_key("character", nc.character_id)
                if key:
                    rows.append(RefRow("character", key, "appears", "character_ids"))
            if n.location_id:
                key = ctx.entity_key("lore", n.location_id)
                if key:
                    rows.append(RefRow("lore", key, "location", "location_id"))
        case "choice":
            c: Choice = obj
            rows += _expr_rows(c.condition, ctx.scope(Context.CONDITION), "condition", "condition")
            rows += _expr_rows(c.dice, ctx.scope(Context.ROLL), "dice", "dice")
            rows += _effect_rows(c.effects, ctx, "effects")
            if c.min_tier:
                rows.append(RefRow("tier", c.min_tier, "min_tier", "min_tier"))
            for o in c.outcomes:
                if o.target_node_id:
                    key = ctx.node_key(o.target_node_id)
                    if key:
                        rows.append(RefRow("node", key, "outcome", f"outcomes.{o.key}"))
        case "variant":
            v: TextVariant = obj
            rows += _expr_rows(v.condition, ctx.scope(Context.CONDITION), "condition", "condition")
        case "encounter":
            e: Encounter = obj
            for ee in e.enemies:
                key = ctx.entity_key("enemy", ee.enemy_id)
                if key:
                    rows.append(RefRow("enemy", key, "encounter", "enemies", ee.count))
            if e.table_id:
                key = ctx.entity_key("table", e.table_id)
                if key:
                    rows.append(RefRow("table", key, "encounter", "table_id"))
        case "enemy":
            en: Enemy = obj
            formula_scope = ctx.scope(Context.ENEMY_FORMULA)
            for stat, src in sorted(en.stat_formulas.items()):
                rows.append(RefRow("stat", stat, "formula", f"stat_formulas.{stat}"))
                rows += _expr_rows(src, formula_scope, "formula", f"stat_formulas.{stat}")
            if en.lore_entry_id:
                key = ctx.entity_key("lore", en.lore_entry_id)
                if key:
                    rows.append(RefRow("lore", key, "lore", "lore_entry_id"))
            for i, loot in enumerate(en.loot):
                if loot.get("item"):
                    rows.append(
                        RefRow("item", loot["item"], "loot", f"loot[{i}]", loot.get("qty", 1))
                    )
        case "item":
            it: Item = obj
            amount = ctx.scope(Context.AMOUNT)
            for i, m in enumerate(it.modifiers):
                if m.get("stat"):
                    rows.append(RefRow("stat", m["stat"], "modifier", f"modifiers[{i}]"))
                rows += _expr_rows(m.get("amount"), amount, "modifier", f"modifiers[{i}]")
            rows += _effect_rows(it.use_effects, ctx, "use_effects")
        case "table":
            t: RandomTable = obj
            rows += _expr_rows(t.dice, ctx.scope(Context.ROLL), "dice", "dice")
            for i, entry in enumerate(t.entries):
                f = f"entries[{i}]"
                for te in entry.get("enemies", []):
                    rows.append(RefRow("enemy", te["enemy"], "table", f, te.get("count", 1)))
                if entry.get("item"):
                    rows.append(RefRow("item", entry["item"], "table", f, entry.get("qty", 1)))
                rows += _expr_rows(entry.get("amount"), ctx.scope(Context.AMOUNT), "table", f)
        case "character":
            ch: Character = obj
            for i, rel in enumerate(ch.relationships):
                if rel.get("character"):
                    rows.append(
                        RefRow("character", rel["character"], "relationship", f"relationships[{i}]")
                    )
    return rows


def _resolve_id(ctx: RefContext, row: RefRow, book_id: str | None) -> str | None:
    if row.target_type in _ENTITY_MODELS:
        model = _ENTITY_MODELS[row.target_type]
        return ctx.session.scalar(
            select(model.id).where(model.series_id == ctx.series_id, model.key == row.target_key)
        )
    if row.target_type == "node" and book_id:
        return ctx.session.scalar(
            select(Node.id).where(Node.book_id == book_id, Node.key == row.target_key)
        )
    return None


def _location(source_type: SourceType, obj: Any, session: Session) -> tuple[str | None, str | None]:
    """(book_id, node_id) for a source."""
    match source_type:
        case "node":
            return obj.book_id, obj.id
        case "choice" | "variant" | "encounter":
            node = session.get(Node, obj.node_id)
            return (node.book_id if node else None), obj.node_id
        case _:
            return obj.book_id, None


def reindex(
    session: Session, source_type: SourceType, obj: Any, ctx: RefContext | None = None
) -> None:
    """Replace the RefIndex rows for one source."""
    book_id, node_id = _location(source_type, obj, session)
    series_id = _series_of(session, source_type, obj, book_id)
    ctx = ctx or RefContext(session, series_id)
    drop(session, source_type, [obj.id])
    for row in extract(source_type, obj, ctx):
        session.add(
            RefIndex(
                series_id=series_id,
                book_id=book_id,
                source_type=source_type,
                source_id=obj.id,
                node_id=node_id,
                target_type=row.target_type,
                target_key=row.target_key,
                target_id=_resolve_id(ctx, row, book_id),
                role=row.role,
                field=row.field,
                qty=row.qty,
            )
        )
    session.flush()


def _series_of(session: Session, source_type: SourceType, obj: Any, book_id: str | None) -> str:
    if source_type in ("enemy", "item", "table", "character"):
        return str(obj.series_id)
    book = session.get(Book, book_id)
    assert book is not None
    return book.series_id


def reindex_node_tree(session: Session, node: Node, ctx: RefContext | None = None) -> None:
    """Reindex a node and everything hanging off it."""
    ctx = ctx or RefContext(session, node.book.series_id)
    reindex(session, "node", node, ctx)
    for c in node.choices:
        reindex(session, "choice", c, ctx)
    for v in node.variants:
        reindex(session, "variant", v, ctx)
    for e in node.encounters:
        reindex(session, "encounter", e, ctx)


def drop(session: Session, source_type: str, ids: Iterable[str]) -> None:
    ids = list(ids)
    if ids:
        session.execute(
            delete(RefIndex).where(RefIndex.source_type == source_type, RefIndex.source_id.in_(ids))
        )


def drop_node_tree(session: Session, node: Node) -> None:
    drop(session, "node", [node.id])
    drop(session, "choice", [c.id for c in node.choices])
    drop(session, "variant", [v.id for v in node.variants])
    drop(session, "encounter", [e.id for e in node.encounters])


def rebuild_series(session: Session, series_id: str) -> None:
    """Recompute every RefIndex row in a series from scratch."""
    session.execute(delete(RefIndex).where(RefIndex.series_id == series_id))
    session.flush()
    ctx = RefContext(session, series_id)
    nodes = session.scalars(
        select(Node)
        .join(Book, Node.book_id == Book.id)
        .where(Book.series_id == series_id)
        .options(
            selectinload(Node.choices).selectinload(Choice.outcomes),
            selectinload(Node.variants),
            selectinload(Node.encounters).selectinload(Encounter.enemies),
            selectinload(Node.items),
            selectinload(Node.shop_items),
            selectinload(Node.characters),
        )
    )
    for node in nodes:
        reindex_node_tree(session, node, ctx)
    for kind, model in (
        ("enemy", Enemy),
        ("item", Item),
        ("table", RandomTable),
        ("character", Character),
    ):
        for obj in session.scalars(select(model).where(model.series_id == series_id)):
            reindex(session, kind, obj, ctx)  # type: ignore[arg-type]


# ── queries ──────────────────────────────────────────────────────────────


def where_used(
    session: Session, series_id: str, target_type: str, target_key: str
) -> list[tuple[RefIndex, str | None]]:
    """References to a target, with the title of the node they live on."""
    stmt = (
        select(RefIndex, Node.title)
        .outerjoin(Node, Node.id == RefIndex.node_id)
        .where(
            RefIndex.series_id == series_id,
            RefIndex.target_type == target_type,
            RefIndex.target_key == target_key,
        )
        .order_by(RefIndex.book_id, Node.title, RefIndex.id)
    )
    return [(r, t) for r, t in session.execute(stmt).all()]


def flag_usage(session: Session, series_id: str) -> dict[str, dict[str, int]]:
    rows = session.execute(
        select(RefIndex.target_key, RefIndex.role).where(
            RefIndex.series_id == series_id, RefIndex.target_type == "flag"
        )
    )
    out: dict[str, dict[str, int]] = {}
    for key, role in rows:
        bucket = out.setdefault(key, {"set": 0, "cleared": 0, "tested": 0})
        if role == "effect.set_flag":
            bucket["set"] += 1
        elif role == "effect.clear_flag":
            bucket["cleared"] += 1
        else:
            bucket["tested"] += 1
    return dict(sorted(out.items()))


def flags_set_in_series(session: Session, series_id: str) -> frozenset[str]:
    return frozenset(
        session.scalars(
            select(RefIndex.target_key).where(
                RefIndex.series_id == series_id,
                RefIndex.target_type == "flag",
                RefIndex.role == "effect.set_flag",
            )
        )
    )


# ── renames ──────────────────────────────────────────────────────────────


def rename_key(
    session: Session,
    series_id: str,
    kind: RefKind | str,
    old: str,
    new: str,
    *,
    book_id: str | None = None,
) -> int:
    """Rewrite every keyed reference ``old`` → ``new``. Returns sources changed.

    ``book_id`` limits the rename to one book — required for node keys, which
    are only unique within a book.
    """
    kind_value = kind.value if isinstance(kind, RefKind) else kind
    stmt = select(RefIndex.source_type, RefIndex.source_id).where(
        RefIndex.series_id == series_id,
        RefIndex.target_type == kind_value,
        RefIndex.target_key == old,
    )
    if book_id is not None:
        stmt = stmt.where(RefIndex.book_id == book_id)
    sources = session.execute(stmt.distinct()).all()
    ctx = RefContext(session, series_id)
    ref_kind = RefKind(kind_value) if kind_value in RefKind._value2member_map_ else None
    models: dict[str, type[Any]] = {
        "node": Node,
        "choice": Choice,
        "variant": TextVariant,
        "encounter": Encounter,
        "enemy": Enemy,
        "item": Item,
        "table": RandomTable,
        "character": Character,
    }
    changed = 0
    for source_type, source_id in sources:
        obj = session.get(models[source_type], source_id)
        if obj is None:
            continue
        _rename_in(source_type, obj, ctx, kind_value, ref_kind, old, new)
        changed += 1
    session.flush()
    # Reindex everything that pointed at the old key (keys or FKs).
    for source_type, source_id in sources:
        obj = session.get(models[source_type], source_id)
        if obj is not None:
            session.refresh(obj)
            reindex(session, cast(SourceType, source_type), obj, RefContext(session, series_id))
    return changed


def _rename_expr(
    src: str | None, scope: Scope, kind: RefKind | None, old: str, new: str
) -> str | None:
    if src is None or kind is None:
        return src
    return gbx.rename_in_source(src, scope, kind, old, new)


def _rename_effects(
    raw: list[dict[str, Any]], scope: Scope, kind: RefKind | None, old: str, new: str
) -> list[dict[str, Any]]:
    if kind is None:
        return raw
    try:
        effects = _EFFECTS.validate_python(raw)
    except ValidationError:
        return raw
    return dump_effects([rename_in_effect(e, scope, kind, old, new) for e in effects])


def _rename_in(
    source_type: str,
    obj: Any,
    ctx: RefContext,
    kind: str,
    ref_kind: RefKind | None,
    old: str,
    new: str,
) -> None:
    cond = ctx.scope(Context.CONDITION)
    amount = ctx.scope(Context.AMOUNT)
    if source_type == "node":
        obj.on_enter = _rename_effects(obj.on_enter, amount, ref_kind, old, new)
    elif source_type == "choice":
        obj.condition = _rename_expr(obj.condition, cond, ref_kind, old, new)
        obj.dice = _rename_expr(obj.dice, ctx.scope(Context.ROLL), ref_kind, old, new)
        obj.effects = _rename_effects(obj.effects, amount, ref_kind, old, new)
        if kind == "tier" and obj.min_tier == old:
            obj.min_tier = new
    elif source_type == "variant":
        obj.condition = _rename_expr(obj.condition, cond, ref_kind, old, new)
    elif source_type == "item":
        mods = []
        for m in obj.modifiers:
            m = dict(m)
            m["amount"] = _rename_expr(m.get("amount"), amount, ref_kind, old, new)
            if kind == "stat" and m.get("stat") == old:
                m["stat"] = new
            mods.append(m)
        obj.modifiers = mods
        obj.use_effects = _rename_effects(obj.use_effects, amount, ref_kind, old, new)
    elif source_type == "enemy":
        if kind == "item":
            obj.loot = [
                {**loot, "item": new} if loot.get("item") == old else loot for loot in obj.loot
            ]
    elif source_type == "table":
        entries = []
        for entry in obj.entries:
            entry = dict(entry)
            if kind == "enemy":
                entry["enemies"] = [
                    {**te, "enemy": new} if te.get("enemy") == old else te
                    for te in entry.get("enemies", [])
                ]
            if kind == "item" and entry.get("item") == old:
                entry["item"] = new
            entry["amount"] = _rename_expr(entry.get("amount"), amount, ref_kind, old, new)
            entries.append(entry)
        obj.entries = entries
        obj.dice = _rename_expr(obj.dice, ctx.scope(Context.ROLL), ref_kind, old, new) or obj.dice
    elif source_type == "character" and kind == "character":
        obj.relationships = [
            {**r, "character": new} if r.get("character") == old else r for r in obj.relationships
        ]
