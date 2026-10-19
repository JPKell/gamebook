"""Appendices: generated back matter, rendered from live data (SPEC §2.14).

Each kind gathers its data here, tier-aware and spoiler-aware, and renders through
``gamebook.render`` templates shared by the preview, print and the player's codex.
In the codex, bestiary and item entries appear only once the reader has met them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gamebook.core import gbx
from gamebook.core.analysis import digest as digest_mod
from gamebook.core.effects import effect_to_english
from gamebook.core.engine.combat import enemy_stats
from gamebook.core.gbx.scope import RefKind
from gamebook.core.model import BookSnapshot
from gamebook.core.rules.schema import EffectiveTier, TierError, effective_tier
from gamebook.db.models import (
    Appendix,
    ArtPlacement,
    Asset,
    Book,
    Character,
    Enemy,
    Item,
    LoreEntry,
    Map,
    RefIndex,
)
from gamebook.render import appendix as render
from gamebook.schemas.art import AppendixIn, AppendixOptions, AppendixUpdate, CodexIn
from gamebook.services import snapshot
from gamebook.services.common import require
from gamebook.services.errors import InvalidError

DEFAULT_TITLES = {
    "bestiary": "Bestiary",
    "sheet": "Adventure Sheet",
    "items": "Items",
    "rules": "Rules Reference",
    "personae": "Dramatis Personae",
    "glossary": "Glossary",
    "maps": "Maps",
    "custom": "Notes",
}
#: Kinds the codex unlocks entry by entry as the reader meets them.
UNLOCKED_BY_PLAY = frozenset({"bestiary", "items"})

# ── CRUD ──────────────────────────────────────────────────────────────────


def list_appendices(session: Session, book_id: str) -> list[Appendix]:
    require(session, Book, book_id)
    return list(
        session.scalars(
            select(Appendix).where(Appendix.book_id == book_id).order_by(Appendix.position)
        )
    )


def _check_options(session: Session, book: Book, opts: AppendixOptions) -> None:
    from gamebook.services.art import check_tier  # local: art imports more of services

    check_tier(session, book.series_id, opts.tier, "options.tier")


def create(session: Session, book_id: str, data: AppendixIn) -> Appendix:
    book = require(session, Book, book_id)
    _check_options(session, book, data.options)
    position = (
        session.scalar(select(func.max(Appendix.position)).where(Appendix.book_id == book_id)) or 0
    ) + 1
    a = Appendix(
        book_id=book_id,
        kind=data.kind,
        title=data.title or DEFAULT_TITLES[data.kind],
        position=position,
        enabled=True,
        options=data.options.model_dump(),
    )
    session.add(a)
    session.flush()
    return a


def update(session: Session, appendix_id: str, data: AppendixUpdate) -> Appendix:
    a = require(session, Appendix, appendix_id)
    if data.title is not None:
        a.title = data.title
    if data.enabled is not None:
        a.enabled = data.enabled
    if data.options is not None:
        _check_options(session, require(session, Book, a.book_id), data.options)
        a.options = data.options.model_dump()
    session.flush()
    return a


def delete(session: Session, appendix_id: str) -> None:
    session.delete(require(session, Appendix, appendix_id))
    session.flush()


def reorder(session: Session, book_id: str, ids: list[str]) -> list[Appendix]:
    rows = list_appendices(session, book_id)
    by_id = {a.id: a for a in rows}
    if sorted(ids) != sorted(by_id):
        raise InvalidError("Send every appendix of the book exactly once", field="ids")
    for pos, i in enumerate(ids, start=1):
        by_id[i].position = pos
    session.flush()
    return sorted(rows, key=lambda a: a.position)


# ── data ──────────────────────────────────────────────────────────────────


@dataclass
class _Ctx:
    session: Session
    book: Book
    snap: BookSnapshot
    tier: EffectiveTier | None
    tiers: tuple[str, ...]
    opts: AppendixOptions
    #: Node ids in scope (spoiler policy), in canonical order.
    nodes: list[str]
    asset_url: Callable[[str], str]
    codex: CodexIn | None


def _tier(snap: BookSnapshot, wanted: str | None) -> tuple[EffectiveTier | None, tuple[str, ...]]:
    if snap.rules is None:
        return None, ()
    keys = snap.rules.tier_keys()
    key = wanted if wanted in keys else keys[-1]  # default: the highest tier
    try:
        return effective_tier(snap.rules, key), keys
    except TierError:
        return None, keys


def _scope(snap: BookSnapshot, tier: str | None, policy: str) -> list[str]:
    """Node ids in canonical order; for ``met_on_canonical_path``, only the main path.

    The main path is every node on a canonical-predecessor chain from the start to
    a victory ending (all reachable nodes when the book has no victory yet).
    """
    d = digest_mod.compute(snap, tier)
    acts = snap.act_index()

    def order(nid: str) -> tuple[int, float, str]:
        n = snap.node(nid)
        nd = d.nodes.get(nid)
        depth = nd.depth_min if nd and nd.depth_min is not None else float("inf")
        return (acts.get(n.act_id, 0) if n else 0, depth, n.title.lower() if n else "")

    ids = [n.id for n in snap.nodes]
    if policy == "met_on_canonical_path":
        reachable = {nid for nid, nd in d.nodes.items() if nd.reachable}
        wins = [n.id for n in snap.nodes if n.ending_kind == "victory" and n.id in reachable]
        if wins:
            path: set[str] = set()
            for w in wins:
                cur: str | None = w
                while cur and cur not in path:
                    path.add(cur)
                    n = snap.node(cur)
                    nd = d.nodes.get(cur)
                    cur = (n.canonical_predecessor_id if n else None) or (
                        nd.canonical_predecessor if nd else None
                    )
            ids = [i for i in ids if i in path]
        else:
            ids = [i for i in ids if i in reachable]
    return sorted(ids, key=order)


def _images(
    session: Session, column: str, ids: list[str], asset_url: Callable[[str], str]
) -> dict[str, dict[str, str]]:
    """Entity id → first portrait (or image) with an asset: {url, alt}."""
    if not ids:
        return {}
    col = getattr(ArtPlacement, column)
    rows = session.execute(
        select(col, ArtPlacement.role, Asset.id, Asset.alt_text)
        .join(Asset, Asset.id == ArtPlacement.asset_id)
        .where(col.in_(ids))
        .order_by(ArtPlacement.role.desc(), ArtPlacement.position)  # portrait before image
    )
    out: dict[str, dict[str, str]] = {}
    for eid, _role, aid, alt in rows:
        url = asset_url(aid)
        if url:  # empty: the file is missing (e.g. an EPUB built without it)
            out.setdefault(eid, {"url": url, "alt": alt})
    return out


def _namer(snap: BookSnapshot, tier: EffectiveTier | None) -> Callable[[RefKind, str], str]:
    items = {i.key: i.name for i in snap.items}

    def name(kind: RefKind, key: str) -> str:
        if kind == RefKind.ITEM:
            return items.get(key, key)
        if tier is not None:
            if kind == RefKind.STAT and key in tier.stats:
                return tier.stats[key].label
            if kind == RefKind.SKILL and key in tier.skills:
                return tier.skills[key].label
        return key.upper() if kind == RefKind.FLAG else key

    return name


def _english(
    src: str | None,
    namer: Callable[[RefKind, str], str],
    tiers: tuple[str, ...],
    *,
    cond: bool = False,
) -> str:
    if not src:
        return ""
    try:
        expr = gbx.parse(src)
    except gbx.GbxSyntaxError:
        return src
    try:
        if cond:
            return gbx.condition_to_english(expr, namer, tiers=tiers)
        return gbx.number_to_english(expr, namer, tiers=tiers)
    except Exception:  # an unusual expression: show it as written
        return src


def _bestiary(c: _Ctx) -> dict[str, Any]:
    snap = c.snap
    enemies = {e.key: e for e in snap.enemies if snap.available(e)}
    by_id = {e.id: e for e in snap.enemies}
    tables = {t.id: t for t in snap.tables}
    levels: dict[str, set[int]] = {}
    first: dict[str, int] = {}
    for idx, nid in enumerate(c.nodes):
        n = snap.node(nid)
        if n is None:
            continue
        for enc in n.encounters:
            found: list[tuple[str, int]] = []
            for ee in enc.enemies:
                if ee.enemy_id in by_id:
                    found.append((by_id[ee.enemy_id].key, ee.level))
            if enc.table_id and enc.table_id in tables:
                for entry in tables[enc.table_id].entries:
                    found += [(key, level) for key, level, _count in entry.enemies]
            for key, level in found:
                if key in enemies:
                    levels.setdefault(key, set()).add(level)
                    first.setdefault(key, idx)
    keys = list(levels)
    if c.codex is not None:
        met = set(c.codex.enemies)
        keys = [k for k in keys if k in met]
    rows = {
        r.id: r
        for r in c.session.scalars(select(Enemy).where(Enemy.id.in_([enemies[k].id for k in keys])))
    }
    lore_names = dict(
        c.session.execute(
            select(LoreEntry.id, LoreEntry.name).where(
                LoreEntry.id.in_({r.lore_entry_id for r in rows.values() if r.lore_entry_id})
            )
        ).all()
    )
    images = (
        _images(c.session, "enemy_id", [enemies[k].id for k in keys], c.asset_url)
        if c.opts.show_images
        else {}
    )
    stat_keys = [k for k, s in (c.tier.stats.items() if c.tier else []) if "enemy" in s.applies_to]
    labels = {k: c.tier.stats[k].label for k in stat_keys} if c.tier else {}
    entries = []
    for key in keys:
        e = enemies[key]
        row = rows.get(e.id)
        blocks = []
        for level in sorted(levels[key]):
            stats = (
                enemy_stats(e.stat_formulas, level, frozenset(stat_keys), c.tiers, c.tier.key)
                if c.tier
                else {}
            )
            blocks.append(
                {
                    "level": level,
                    "stats": [
                        {
                            "label": labels[s],
                            "value": None if c.opts.blank_entries else stats.get(s, 0),
                        }
                        for s in stat_keys
                    ],
                }
            )
        entries.append(
            {
                "key": key,
                "name": e.name,
                "description": "" if c.opts.blank_entries else (row.description if row else ""),
                "lore": lore_names.get(row.lore_entry_id or "") if row else None,
                "image": images.get(e.id),
                "levels": blocks,
            }
        )
    if c.opts.order == "alpha":
        entries.sort(key=lambda x: str(x["name"]).lower())
    else:
        entries.sort(key=lambda x: first.get(str(x["key"]), 0))
    return {
        "entries": entries,
        "stat_labels": [labels[s] for s in stat_keys],
        "table": c.opts.stat_mode == "table",
        "total": len(levels),
    }


def _sheet(c: _Ctx) -> dict[str, Any]:
    t = c.tier
    if t is None:
        return {
            "stats": [],
            "skills": [],
            "classes": [],
            "slots": [],
            "currency": None,
            "codewords": [],
            "inventory_lines": c.opts.inventory_lines,
            "blank_codewords": True,
        }
    namer = _namer(c.snap, t)
    stats = []
    currency = None
    for s in t.stats.values():
        if "player" not in s.applies_to:
            continue
        if s.kind == "resource" and currency is None:
            currency = s.label
            continue
        stats.append(
            {
                "label": s.label,
                "initial": _english(s.initial, namer, c.tiers),
                "has_max": s.max is not None or s.max_is_initial,
            }
        )
    flags = sorted(
        set(
            c.session.scalars(
                select(RefIndex.target_key).where(
                    RefIndex.book_id == c.book.id,
                    RefIndex.target_type == "flag",
                    RefIndex.role == "effect.set_flag",
                )
            )
        )
    )
    return {
        "stats": stats,
        "skills": [s.label for s in t.skills.values()],
        "classes": [
            {"label": cl.label, "description": cl.description} for cl in t.classes.values()
        ],
        "slots": list(t.slots),
        "currency": currency,
        "codewords": [f.upper() for f in flags] if c.opts.codewords == "list" else [],
        "blank_codewords": c.opts.codewords == "blank",
        "inventory_lines": c.opts.inventory_lines,
    }


def _items(c: _Ctx) -> dict[str, Any]:
    snap = c.snap
    available = [i for i in snap.items if snap.available(i)]
    if c.opts.hide_key_items:
        available = [i for i in available if i.category != "key"]
    total = len(available)
    # Where each item first turns up, in canonical order (for ordering and spoilers).
    order = {nid: n for n, nid in enumerate(c.nodes)}
    first: dict[str, int] = {}
    for key, nid in c.session.execute(
        select(RefIndex.target_key, RefIndex.node_id).where(
            RefIndex.book_id == c.book.id, RefIndex.target_type == "item"
        )
    ):
        if nid in order:
            first[key] = min(first.get(key, order[nid]), order[nid])
    if c.opts.spoilers == "met_on_canonical_path":
        available = [i for i in available if i.key in first]
    if c.codex is not None:
        met = set(c.codex.items)
        available = [i for i in available if i.key in met]
    rows = {
        r.id: r
        for r in c.session.scalars(select(Item).where(Item.id.in_([i.id for i in available])))
    }
    images = (
        _images(c.session, "item_id", [i.id for i in available], c.asset_url)
        if c.opts.show_images
        else {}
    )
    namer = _namer(snap, c.tier)
    tier_index = {k: n for n, k in enumerate(c.tiers)}
    here = tier_index.get(c.tier.key, len(c.tiers)) if c.tier else len(c.tiers)
    entries = []
    for i in available:
        row = rows.get(i.id)
        mods = []
        for m in i.modifiers:
            if m.min_tier and tier_index.get(m.min_tier, 0) > here:
                continue
            if c.tier is not None and m.stat not in c.tier.stats:
                continue
            label = c.tier.stats[m.stat].label if c.tier else m.stat
            amount = _english(m.amount, namer, c.tiers)
            sign = "" if amount.startswith(("-", "minus")) else "+"
            mods.append(f"{label} {sign}{amount}")
        entries.append(
            {
                "name": i.name,
                "category": i.category,
                "slot": i.slot,
                "value": i.value or None,
                "description": "" if c.opts.blank_entries else (row.description if row else ""),
                "modifiers": [] if c.opts.blank_entries else mods,
                "uses": []
                if c.opts.blank_entries
                else [effect_to_english(e, namer) for e in i.use_effects],
                "image": images.get(i.id),
            }
        )
    if c.opts.order == "first_appearance":
        keys = {i.name: i.key for i in available}
        entries.sort(key=lambda x: first.get(keys.get(str(x["name"]), ""), len(order)))
    else:
        entries.sort(key=lambda x: str(x["name"]).lower())
    return {"entries": entries, "total": total}


def _rules(c: _Ctx) -> dict[str, Any]:
    t = c.tier
    if t is None:
        return {"tier": None, "tests": [], "combat": None, "text": ""}
    namer = _namer(c.snap, t)
    tests = [
        {
            "label": d.label,
            "roll": _english(d.roll, namer, c.tiers),
            "success": _english(d.success, namer, c.tiers, cond=True),
            "description": d.description,
            "after": [effect_to_english(e, namer) for e in d.after],
        }
        for d in t.tests.values()
    ]
    cb = t.combat
    combat = None
    if cb.player_attack or cb.damage_stat:
        combat = {
            "player_attack": _english(cb.player_attack, namer, c.tiers),
            "enemy_attack": _english(cb.enemy_attack, namer, c.tiers),
            "damage": _english(cb.damage, namer, c.tiers),
            "damage_stat": t.stats[cb.damage_stat].label
            if cb.damage_stat in t.stats
            else cb.damage_stat,
            "hooks": [_english(h, namer, c.tiers) for h in cb.damage_hooks],
            "multi": cb.multi_enemy or "sequential",
            "flee": bool(cb.flee_allowed),
            "flee_cost": [effect_to_english(e, namer) for e in (cb.flee_cost or [])],
        }
    texts = [
        td.rules_text
        for td in (c.snap.rules.tiers if c.snap.rules else [])
        if td.key in c.tiers[: c.tiers.index(t.key) + 1]
    ]
    return {
        "tier": t.label,
        "tests": tests,
        "combat": combat,
        "text": render.markdown("\n\n".join(x for x in texts if x.strip())),
    }


def _personae(c: _Ctx) -> dict[str, Any]:
    snap = c.snap
    chars = [ch for ch in snap.characters if snap.available(ch)]
    if c.opts.spoilers == "met_on_canonical_path":
        scope = {snap.node(n) for n in c.nodes}
        met = {cid for n in scope if n for cid in n.character_ids}
        chars = [ch for ch in chars if ch.id in met]
    rows = {
        r.id: r
        for r in c.session.scalars(select(Character).where(Character.id.in_([x.id for x in chars])))
    }
    images = (
        _images(c.session, "character_id", [x.id for x in chars], c.asset_url)
        if c.opts.show_images
        else {}
    )
    entries = [
        {
            "name": ch.name,
            "role": rows[ch.id].role if ch.id in rows else "",
            "description": ""
            if c.opts.blank_entries
            else (rows[ch.id].appearance if ch.id in rows else ""),
            "image": images.get(ch.id),
        }
        for ch in chars
    ]
    entries.sort(key=lambda x: str(x["name"]).lower())
    return {"entries": entries}


def _glossary(c: _Ctx) -> dict[str, Any]:
    rows = list(
        c.session.scalars(
            select(LoreEntry).where(
                LoreEntry.series_id == c.book.series_id,
                LoreEntry.type == "glossary",
                (LoreEntry.book_id.is_(None)) | (LoreEntry.book_id == c.book.id),
            )
        )
    )
    resolve = _resolver(c)
    return {
        "entries": sorted(
            ({"name": r.name, "body": render.markdown(r.body, resolve)} for r in rows),
            key=lambda x: str(x["name"]).lower(),
        )
    }


def _maps(c: _Ctx) -> dict[str, Any]:
    q = select(Map).where(
        Map.series_id == c.book.series_id, (Map.book_id.is_(None)) | (Map.book_id == c.book.id)
    )
    maps = list(c.session.scalars(q.order_by(Map.title)))
    if c.opts.map_ids:
        wanted = set(c.opts.map_ids)
        maps = [m for m in maps if m.id in wanted]
    alts = dict(
        c.session.execute(
            select(Asset.id, Asset.alt_text).where(
                Asset.id.in_({m.asset_id for m in maps if m.asset_id})
            )
        ).all()
    )
    return {
        "maps": [
            {
                "title": m.title,
                "image": {"url": c.asset_url(m.asset_id), "alt": alts.get(m.asset_id, "")}
                if m.asset_id and c.asset_url(m.asset_id)
                else None,
                "markers": [
                    {
                        "n": i + 1,
                        "x": mk["x"] * 100,
                        "y": mk["y"] * 100,
                        "label": mk.get("label", ""),
                    }
                    for i, mk in enumerate(
                        mk
                        for mk in m.markers
                        # Hidden markers (revealed by codewords) are spoilers; the codex
                        # never shows them (the player's map shows the ones revealed).
                        if (c.opts.spoilers == "all" and c.codex is None)
                        or not mk.get("visible_if")
                    )
                ],
            }
            for m in maps
        ]
    }


def _resolver(c: _Ctx) -> Callable[[str | None, str], str | None]:
    names: dict[tuple[str, str], str] = {}
    for kind, model in (("character", Character), ("lore", LoreEntry)):
        for key, name in c.session.execute(
            select(model.key, model.name).where(model.series_id == c.book.series_id)
        ):
            names[(kind, key)] = name

    def resolve(kind: str | None, key: str) -> str | None:
        if kind:
            return names.get((kind, key))
        return names.get(("character", key)) or names.get(("lore", key))

    return resolve


def _custom(c: _Ctx) -> dict[str, Any]:
    return {"body": render.markdown(c.opts.body, _resolver(c))}


_BUILDERS: dict[str, Callable[[_Ctx], dict[str, Any]]] = {
    "bestiary": _bestiary,
    "sheet": _sheet,
    "items": _items,
    "rules": _rules,
    "personae": _personae,
    "glossary": _glossary,
    "maps": _maps,
    "custom": _custom,
}


def default_asset_url(asset_id: str) -> str:
    return f"/api/assets/{asset_id}/file"


def render_kind(
    session: Session,
    book: Book,
    kind: str,
    title: str,
    options: AppendixOptions,
    *,
    snap: BookSnapshot,
    codex: CodexIn | None = None,
    asset_url: Callable[[str], str] = default_asset_url,
) -> str:
    """One appendix of any kind as an HTML fragment (also used by print's front matter)."""
    opts = options
    if codex is not None:
        # The reader's tier for every page; what they've met decides the bestiary and
        # items, so those show everything met wherever it was (other kinds keep the
        # author's spoiler policy).
        update: dict[str, Any] = {"tier": codex.tier, "blank_entries": False}
        if kind in UNLOCKED_BY_PLAY:
            update["spoilers"] = "all"
        opts = opts.model_copy(update=update)
    tier, tiers = _tier(snap, opts.tier)
    nodes = _scope(snap, tier.key if tier else None, opts.spoilers)
    ctx = _Ctx(session, book, snap, tier, tiers, opts, nodes, asset_url, codex)
    return render.fragment(kind, title, _BUILDERS[kind](ctx), codex=codex is not None)


def render_appendix(
    session: Session,
    appendix_id: str,
    *,
    codex: CodexIn | None = None,
    asset_url: Callable[[str], str] = default_asset_url,
    snap: BookSnapshot | None = None,
) -> tuple[str, str]:
    """(title, HTML fragment) for one appendix."""
    a = require(session, Appendix, appendix_id)
    book = require(session, Book, a.book_id)
    opts = AppendixOptions.model_validate(a.options or {})
    snap = snap or snapshot.book_snapshot(session, book.id)
    html = render_kind(
        session, book, a.kind, a.title, opts, snap=snap, codex=codex, asset_url=asset_url
    )
    return a.title, html


def render_document(session: Session, appendix_id: str) -> tuple[str, str, str]:
    """(title, fragment, standalone HTML document) for the preview."""
    title, fragment = render_appendix(session, appendix_id)
    return title, fragment, render.document(title, fragment)


def codex(session: Session, book_id: str, data: CodexIn) -> list[tuple[str, str, str]]:
    """The book's enabled appendices as the player's codex: (id, title, document)."""
    snap = snapshot.book_snapshot(session, book_id)
    if snap.rules is None or data.tier not in snap.rules.tier_keys():
        raise InvalidError(f"Unknown tier {data.tier!r}", field="tier")
    out = []
    for a in list_appendices(session, book_id):
        if not a.enabled or a.kind == "sheet":
            continue
        title, fragment = render_appendix(session, a.id, codex=data, snap=snap)
        out.append((a.id, title, render.document(title, fragment)))
    return out
