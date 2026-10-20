"""Art placements, page setup, maps, the commissioning shot list and art problems.

Node, act and book placements are part of the book's undo history (they travel in
``export_book`` snapshots); entity portraits, maps and the library are not.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gamebook.core import gbx
from gamebook.core.analysis.problems import Problem
from gamebook.core.art import (
    DigitalLayout,
    PageSetup,
    PrintLayout,
    default_layout,
    pixels_needed,
    print_size,
)
from gamebook.core.keys import key_problem
from gamebook.db.models import (
    Act,
    ArtPlacement,
    Asset,
    Book,
    Character,
    Enemy,
    Item,
    LoreEntry,
    Map,
    Node,
    RefIndex,
    Series,
    TextVariant,
)
from gamebook.schemas.art import (
    ArtPlacementIn,
    ArtPlacementUpdate,
    MapIn,
    MapUpdate,
    ShotRow,
)
from gamebook.services import history, refs
from gamebook.services.assets import asset_out
from gamebook.services.common import require
from gamebook.services.errors import ConflictError, InvalidError

TARGET_MODELS: dict[str, type[Any]] = {
    "node": Node,
    "act": Act,
    "book": Book,
    "character": Character,
    "enemy": Enemy,
    "item": Item,
    "lore": LoreEntry,
}
_COLUMN = {
    "node": "node_id",
    "act": "act_id",
    "book": "book_id",
    "character": "character_id",
    "enemy": "enemy_id",
    "item": "item_id",
    "lore": "lore_id",
}
ROLE_LABELS = {
    "illustration": "Illustration",
    "opener": "Act opener",
    "cover_front": "Front cover",
    "cover_back": "Back cover",
    "frontispiece": "Frontispiece",
    "title_page": "Title page",
    "endpaper": "Endpaper",
    "portrait": "Portrait",
    "image": "Image",
}

# ── page setup ────────────────────────────────────────────────────────────


def page_setup(book: Book | None) -> PageSetup:
    return PageSetup.model_validate((book.print_setup if book else None) or {})


def get_page_setup(session: Session, book_id: str) -> PageSetup:
    return page_setup(require(session, Book, book_id))


def save_page_setup(session: Session, book_id: str, data: PageSetup) -> PageSetup:
    book = require(session, Book, book_id)
    if data.inner_mm + data.margin_outer_mm >= data.trim_width_mm - 20:
        raise InvalidError("The side margins leave no room for text", field="margin_inner_mm")
    if data.margin_top_mm + data.margin_bottom_mm >= data.trim_height_mm - 20:
        raise InvalidError("The top and bottom margins leave no room for text")
    history.record(session, book_id, "Edit page setup")
    book.print_setup = data.model_dump()
    session.flush()
    return data


# ── placements ────────────────────────────────────────────────────────────


def target_id(pl: ArtPlacement) -> str:
    return str(getattr(pl, _COLUMN[pl.target_type]))


def target_label(session: Session, pl: ArtPlacement, node_title: str | None = None) -> str:
    role = ROLE_LABELS.get(pl.role, pl.role)
    if pl.target_type == "node":
        title = node_title or session.scalar(select(Node.title).where(Node.id == pl.node_id))
        return f"{role}: {title or 'deleted section'}"
    if pl.target_type == "book":
        return role
    obj = session.get(TARGET_MODELS[pl.target_type], target_id(pl))
    name = getattr(obj, "title", None) or getattr(obj, "name", None) or "deleted"
    kind = {"act": "Act", "character": "Character", "enemy": "Enemy", "item": "Item"}.get(
        pl.target_type, "Lore"
    )
    return f"{role}: {name}" if pl.target_type == "act" else f"{kind} {role.lower()}: {name}"


def _book_of(session: Session, pl: ArtPlacement) -> Book | None:
    if pl.book_id:
        return session.get(Book, pl.book_id)
    return None


def placement_out(
    session: Session,
    pl: ArtPlacement,
    *,
    setup: PageSetup | None = None,
    assets: dict[str, Asset] | None = None,
    node_title: str | None = None,
) -> dict[str, Any]:
    layout = PrintLayout.model_validate(pl.layout or {})
    asset = (assets or {}).get(pl.asset_id or "") if assets is not None else None
    if asset is None and pl.asset_id and assets is None:
        asset = session.get(Asset, pl.asset_id)
    setup = setup or page_setup(_book_of(session, pl))
    size = print_size(
        layout, setup, asset.width_px if asset else None, asset.height_px if asset else None
    )
    return {
        "id": pl.id,
        "series_id": pl.series_id,
        "target_type": pl.target_type,
        "target_id": target_id(pl),
        "target_label": target_label(session, pl, node_title),
        "book_id": pl.book_id,
        "node_id": pl.node_id,
        "act_id": pl.act_id,
        "role": pl.role,
        "asset_id": pl.asset_id,
        "asset": asset_out(asset) if asset else None,
        "variant_id": pl.variant_id,
        "tier": pl.tier,
        "media": pl.media,
        "position": pl.position,
        "caption": pl.caption,
        "brief": pl.brief,
        "status": pl.status,
        "layout": layout,
        "digital": DigitalLayout.model_validate(pl.digital or {}),
        "print_size": {
            "width_mm": size.width_mm,
            "height_mm": size.height_mm,
            "dpi": size.dpi,
            "status": size.status,
            "box_width_mm": size.box_width_mm,
            "box_height_mm": size.box_height_mm,
            "needed_px": pixels_needed(layout, setup),
        },
        "created_at": pl.created_at,
    }


def _series_of_target(obj: Any, target_type: str, session: Session) -> str:
    if target_type in ("node", "act"):
        return require(session, Book, obj.book_id).series_id
    return str(obj.series_id)


def _check_asset(session: Session, series_id: str, asset_id: str | None) -> None:
    if asset_id is None:
        return
    asset = session.get(Asset, asset_id)
    if asset is None or asset.series_id != series_id:
        raise InvalidError("That image isn't in this series' library", field="asset_id")


def check_tier(session: Session, series_id: str, tier: str | None, field: str = "tier") -> None:
    """A tier limit must name one of the active rule system's tiers."""
    if tier is None:
        return
    tiers = refs.RefContext(session, series_id).tiers
    if tier not in tiers:
        known = ", ".join(tiers) or "none (no active rule system)"
        raise InvalidError(f"Unknown tier {tier!r} (tiers: {known})", field=field)


def _record(session: Session, pl: ArtPlacement, label: str) -> None:
    """Node, act and book art is undoable with the book."""
    if pl.target_type in ("node", "act", "book") and pl.book_id:
        history.record(session, pl.book_id, label)


def create_placement(session: Session, data: ArtPlacementIn) -> ArtPlacement:
    model = TARGET_MODELS[data.target_type]
    target = session.get(model, data.target_id)
    if target is None:
        raise InvalidError(f"No {data.target_type} with that id", field="target_id")
    series_id = _series_of_target(target, data.target_type, session)
    _check_asset(session, series_id, data.asset_id)
    check_tier(session, series_id, data.tier)
    if data.variant_id:
        v = session.get(TextVariant, data.variant_id)
        if v is None or v.node_id != data.target_id:
            raise InvalidError("That text variant isn't on this section", field="variant_id")
    role = str(data.role)
    book_id = {
        "node": getattr(target, "book_id", None),
        "act": getattr(target, "book_id", None),
        "book": data.target_id,
    }.get(data.target_type, getattr(target, "book_id", None))
    column = _COLUMN[data.target_type]
    pl = ArtPlacement(
        series_id=series_id,
        target_type=data.target_type,
        role=role,
        asset_id=data.asset_id,
        variant_id=data.variant_id,
        tier=data.tier,
        media=data.media,
        caption=data.caption,
        brief=data.brief,
        status=data.status or ("final" if data.asset_id else "needed"),
        layout=(data.layout or default_layout(role)).model_dump(),
        digital=(data.digital or DigitalLayout()).model_dump(),
    )
    pl.book_id = book_id
    setattr(pl, column, data.target_id)
    pl.position = (
        session.scalar(
            select(func.max(ArtPlacement.position)).where(
                getattr(ArtPlacement, column) == data.target_id
            )
        )
        or 0
    ) + 1
    if pl.target_type in ("node", "act", "book") and book_id:
        history.record(session, book_id, f"Add {ROLE_LABELS[role].lower()}")
    session.add(pl)
    session.flush()
    refs.reindex(session, "placement", pl)
    return pl


def update_placement(session: Session, placement_id: str, data: ArtPlacementUpdate) -> ArtPlacement:
    pl = require(session, ArtPlacement, placement_id)
    changes = data.model_dump(exclude_unset=True)
    if "role" in changes and changes["role"] is not None:
        from gamebook.schemas.art import ROLES_FOR

        if changes["role"] not in ROLES_FOR[pl.target_type]:
            raise InvalidError(f"A {pl.target_type} can't have a {changes['role']}", field="role")
    if "asset_id" in changes:
        _check_asset(session, pl.series_id, changes["asset_id"])
    if changes.get("tier"):
        check_tier(session, pl.series_id, changes["tier"])
    if changes.get("variant_id"):
        v = session.get(TextVariant, changes["variant_id"])
        if pl.target_type != "node" or v is None or v.node_id != pl.node_id:
            raise InvalidError("That text variant isn't on this section", field="variant_id")
    _record(session, pl, f"Edit {ROLE_LABELS.get(pl.role, pl.role).lower()}")
    for k, v in changes.items():
        if k in ("layout", "digital"):
            if v is not None:
                setattr(pl, k, v)
        elif k in ("asset_id", "variant_id", "tier") or v is not None:
            setattr(pl, k, v)
    if (
        "asset_id" in changes
        and changes["asset_id"]
        and pl.status == "needed"
        and "status" not in changes
    ):
        pl.status = "final"
    session.flush()
    refs.reindex(session, "placement", pl)
    return pl


def delete_placement(session: Session, placement_id: str) -> None:
    pl = require(session, ArtPlacement, placement_id)
    _record(session, pl, f"Remove {ROLE_LABELS.get(pl.role, pl.role).lower()}")
    refs.drop(session, "placement", [pl.id])
    session.delete(pl)
    session.flush()


def reorder_placements(session: Session, ids: list[str]) -> list[ArtPlacement]:
    rows = [require(session, ArtPlacement, i) for i in ids]
    if len({target_id(p) for p in rows}) > 1:
        raise InvalidError("Only placements on the same target can be reordered together")
    if rows:
        _record(session, rows[0], "Reorder artwork")
    for pos, p in enumerate(rows, start=1):
        p.position = pos
    session.flush()
    return rows


def list_placements(
    session: Session,
    *,
    series_id: str | None = None,
    book_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
) -> list[dict[str, Any]]:
    q = select(ArtPlacement)
    if series_id:
        q = q.where(ArtPlacement.series_id == series_id)
    if book_id:
        q = q.where(ArtPlacement.book_id == book_id)
    if target_type:
        q = q.where(ArtPlacement.target_type == target_type)
        if target_id:
            q = q.where(getattr(ArtPlacement, _COLUMN[target_type]) == target_id)
    rows = list(session.scalars(q.order_by(ArtPlacement.position, ArtPlacement.created_at)))
    ids = {p.asset_id for p in rows if p.asset_id}
    assets = {a.id: a for a in session.scalars(select(Asset).where(Asset.id.in_(ids)))}
    books = {
        b.id: b
        for b in session.scalars(
            select(Book).where(Book.id.in_({p.book_id for p in rows if p.book_id}))
        )
    }
    setups = {bid: page_setup(b) for bid, b in books.items()}
    default = PageSetup()
    titles = dict(
        session.execute(
            select(Node.id, Node.title).where(Node.id.in_({p.node_id for p in rows if p.node_id}))
        ).all()
    )
    return [
        placement_out(
            session,
            p,
            setup=setups.get(p.book_id or "", default),
            assets=assets,
            node_title=titles.get(p.node_id or ""),
        )
        for p in rows
    ]


def node_thumbs(session: Session, book_id: str) -> dict[str, str]:
    """node id → thumbnail URL of its first illustration with an image (canvas cards)."""
    out: dict[str, str] = {}
    rows = session.execute(
        select(ArtPlacement.node_id, ArtPlacement.asset_id)
        .where(
            ArtPlacement.book_id == book_id,
            ArtPlacement.target_type == "node",
            ArtPlacement.asset_id.is_not(None),
        )
        .order_by(ArtPlacement.position)
    )
    for node_id, asset_id in rows:
        if node_id and node_id not in out:
            out[node_id] = f"/api/assets/{asset_id}/thumb"
    return out


def player_art(
    session: Session, node_id: str, variant_id: str | None, tier: str
) -> list[dict[str, Any]]:
    """Digital artwork for the section a reader is on (their variant and tier only)."""
    rows = session.execute(
        select(ArtPlacement, Asset)
        .join(Asset, Asset.id == ArtPlacement.asset_id)
        .where(
            ArtPlacement.node_id == node_id,
            ArtPlacement.media.in_(("digital", "both")),
            (ArtPlacement.variant_id.is_(None)) | (ArtPlacement.variant_id == variant_id),
            (ArtPlacement.tier.is_(None)) | (ArtPlacement.tier == tier),
        )
        .order_by(ArtPlacement.position)
    )
    out = []
    for pl, asset in rows:
        digital = DigitalLayout.model_validate(pl.digital or {})
        out.append(
            {
                "url": f"/api/assets/{asset.id}/file",
                "thumb_url": f"/api/assets/{asset.id}/thumb",
                "alt": asset.alt_text,
                "caption": pl.caption or asset.caption,
                "display": digital.display,
                "zoom": digital.zoom,
            }
        )
    return out


# ── commissioning ─────────────────────────────────────────────────────────


def shot_list(
    session: Session, series_id: str, *, status: str | None = None, book_id: str | None = None
) -> list[ShotRow]:
    require(session, Series, series_id)
    rows = list_placements(session, series_id=series_id, book_id=book_id)
    books = dict(
        session.execute(select(Book.id, Book.title).where(Book.series_id == series_id)).all()
    )
    out = []
    for p in rows:
        if status and p["status"] != status:
            continue
        size = p["print_size"]
        out.append(
            ShotRow(
                placement_id=p["id"],
                book_id=p["book_id"],
                book_title=books.get(p["book_id"] or ""),
                target_type=p["target_type"],
                target_label=p["target_label"],
                role=p["role"],
                status=p["status"],
                brief=p["brief"],
                has_asset=p["asset_id"] is not None,
                width_mm=size["width_mm"],
                height_mm=size["height_mm"],
                needed_px=size["needed_px"],
                node_id=p["node_id"],
            )
        )
    order = {"needed": 0, "sketch": 1, "final": 2}
    return sorted(out, key=lambda r: (order.get(r.status, 3), r.book_title or "", r.target_label))


def _cell(text: str) -> str:
    """Spreadsheets run cells starting with = + - @ (or a tab/CR) as formulas: quote them."""
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def shot_list_csv(rows: list[ShotRow]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Status", "Book", "Piece", "Brief", "Printed size (mm)", "Pixels at 300 dpi"])
    for r in rows:
        w.writerow(
            [
                r.status,
                _cell(r.book_title or ""),
                _cell(r.target_label),
                _cell(r.brief),
                f"{r.width_mm:g} x {r.height_mm:g}",
                f"{r.needed_px[0]} x {r.needed_px[1]}",
            ]
        )
    return buf.getvalue()


def shot_list_markdown(series_title: str, rows: list[ShotRow]) -> str:
    def cell(text: str) -> str:
        return re.sub(r"\s+", " ", text).replace("|", "\\|").strip() or "—"

    lines = [
        f"# Shot list — {series_title}",
        "",
        "| Status | Book | Piece | Brief | Printed size | Pixels at 300 dpi |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.status} | {cell(r.book_title or '')} | {cell(r.target_label)} | {cell(r.brief)} "
            f"| {r.width_mm:g} x {r.height_mm:g} mm | {r.needed_px[0]} x {r.needed_px[1]} |"
        )
    return "\n".join(lines) + "\n"


# ── maps ──────────────────────────────────────────────────────────────────


def _map_key(session: Session, series_id: str, title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:50] or "map"
    if not base[0].isalpha():
        base = f"map_{base}"
    key, n = base, 2
    while session.scalar(select(Map.id).where(Map.series_id == series_id, Map.key == key)):
        key, n = f"{base}_{n}", n + 1
    return key


def map_out(session: Session, m: Map) -> dict[str, Any]:
    asset = session.get(Asset, m.asset_id) if m.asset_id else None
    return {
        "id": m.id,
        "series_id": m.series_id,
        "book_id": m.book_id,
        "key": m.key,
        "title": m.title,
        "asset_id": m.asset_id,
        "asset": asset_out(asset) if asset else None,
        "markers": m.markers,
    }


def list_maps(session: Session, series_id: str, book_id: str | None = None) -> list[Map]:
    require(session, Series, series_id)
    q = select(Map).where(Map.series_id == series_id)
    if book_id:
        q = q.where((Map.book_id.is_(None)) | (Map.book_id == book_id))
    return list(session.scalars(q.order_by(Map.title)))


def create_map(session: Session, series_id: str, data: MapIn) -> Map:
    require(session, Series, series_id)
    if data.book_id:
        book = require(session, Book, data.book_id)
        if book.series_id != series_id:
            raise InvalidError("That book is in another series", field="book_id")
    _check_asset(session, series_id, data.asset_id)
    key = data.key or _map_key(session, series_id, data.title)
    if session.scalar(select(Map.id).where(Map.series_id == series_id, Map.key == key)):
        raise ConflictError(f"A map with the key {key!r} already exists")
    m = Map(
        series_id=series_id,
        book_id=data.book_id,
        key=key,
        title=data.title,
        asset_id=data.asset_id,
        markers=[],
    )
    session.add(m)
    session.flush()
    refs.reindex(session, "map", m)
    return m


def _check_markers(session: Session, m: Map, markers: list[dict[str, Any]]) -> None:
    ids = [mk["id"] for mk in markers]
    if len(set(ids)) != len(ids):
        raise InvalidError("Marker ids must be unique", field="markers")
    for i, mk in enumerate(markers):
        if mk.get("node_id"):
            node = session.get(Node, mk["node_id"])
            book = session.get(Book, node.book_id) if node else None
            if node is None or book is None or book.series_id != m.series_id:
                raise InvalidError(
                    "A marker links to a section that doesn't exist", field=f"markers[{i}]"
                )
            if m.book_id and node.book_id != m.book_id:
                raise InvalidError(
                    "A marker links to a section in another book", field=f"markers[{i}]"
                )
        if mk.get("lore_id"):
            lore = session.get(LoreEntry, mk["lore_id"])
            if lore is None or lore.series_id != m.series_id:
                raise InvalidError(
                    "A marker links to a lore entry that doesn't exist", field=f"markers[{i}]"
                )
        if mk.get("visible_if"):
            try:
                gbx.parse(mk["visible_if"])
            except gbx.GbxSyntaxError as exc:
                raise InvalidError(
                    f"Marker '{mk.get('label') or i + 1}': {exc}", field=f"markers[{i}].visible_if"
                ) from exc


def update_map(session: Session, map_id: str, data: MapUpdate) -> Map:
    m = require(session, Map, map_id)
    changes = data.model_dump(exclude_unset=True)
    if "asset_id" in changes:
        _check_asset(session, m.series_id, changes["asset_id"])
        m.asset_id = changes["asset_id"]
    if changes.get("key") and changes["key"] != m.key:
        if problem := key_problem(changes["key"]):
            raise InvalidError(problem, field="key")
        if session.scalar(
            select(Map.id).where(Map.series_id == m.series_id, Map.key == changes["key"])
        ):
            raise ConflictError(f"A map with the key {changes['key']!r} already exists")
        m.key = changes["key"]
    if changes.get("title"):
        m.title = changes["title"]
    if "book_id" in changes and changes["book_id"] != m.book_id:
        if changes["book_id"]:
            book = require(session, Book, changes["book_id"])
            if book.series_id != m.series_id:
                raise InvalidError("That book is in another series", field="book_id")
        m.book_id = changes["book_id"]
        if changes.get("markers") is None:  # existing section links must still fit
            _check_markers(session, m, m.markers)
    if changes.get("markers") is not None:
        markers = [
            {k: v for k, v in mk.items() if v not in (None, "")} for mk in changes["markers"]
        ]
        _check_markers(session, m, markers)
        m.markers = markers
    session.flush()
    refs.reindex(session, "map", m)
    return m


def delete_map(session: Session, map_id: str) -> None:
    m = require(session, Map, map_id)
    refs.drop(session, "map", [m.id])
    session.delete(m)
    session.flush()


# ── problems ──────────────────────────────────────────────────────────────


def problems(session: Session, book_id: str) -> list[Problem]:
    """Art problems for a book: DPI, bleed, placeholders, alt text, broken markers, unused."""
    book = require(session, Book, book_id)
    setup = page_setup(book)
    out: list[Problem] = []
    rows = list(
        session.scalars(
            select(ArtPlacement).where(
                ArtPlacement.book_id == book_id,
                ArtPlacement.target_type.in_(("node", "act", "book")),
            )
        )
    )
    assets = {
        a.id: a
        for a in session.scalars(
            select(Asset).where(Asset.id.in_({p.asset_id for p in rows if p.asset_id}))
        )
    }
    node_acts = dict(
        session.execute(select(Node.id, Node.act_id).where(Node.book_id == book_id)).all()
    )
    for p in rows:
        label = target_label(session, p)
        act_id = p.act_id or node_acts.get(p.node_id or "")
        where = {
            "node_id": p.node_id,
            "act_id": act_id,
            "entity_type": "placement",
            "entity_id": p.id,
        }
        asset = assets.get(p.asset_id or "")
        if asset is None:
            out.append(
                Problem(
                    "info", "art_placeholder", f"{label} is a placeholder ({p.status})", **where
                )
            )
            continue
        if not asset.alt_text.strip():
            out.append(
                Problem(
                    "info",
                    "art_alt_text",
                    f"{label}: the image '{asset.filename}' has no alt text",
                    **where,
                )
            )
        if p.media == "digital":
            continue
        layout = PrintLayout.model_validate(p.layout or {})
        size = print_size(layout, setup, asset.width_px, asset.height_px)
        if layout.size == "full_page" and layout.bleed and size.status == "poor":
            out.append(
                Problem(
                    "error",
                    "art_bleed",
                    f"{label}: '{asset.filename}' doesn't cover the page plus bleed at print "
                    f"resolution ({size.dpi:g} dpi; it needs "
                    f"{'x'.join(map(str, pixels_needed(layout, setup)))} px)",
                    **where,
                )
            )
        elif size.status in ("low", "poor"):
            out.append(
                Problem(
                    "error" if size.status == "poor" else "warning",
                    "art_low_dpi",
                    f"{label}: '{asset.filename}' prints at {size.dpi:g} dpi at "
                    f"{size.width_mm:g} x {size.height_mm:g} mm (300 recommended)",
                    **where,
                )
            )
    nodes = set(node_acts)
    series_nodes = set(
        session.scalars(
            select(Node.id)
            .join(Book, Book.id == Node.book_id)
            .where(Book.series_id == book.series_id)
        )
    )
    for m in session.scalars(
        select(Map).where(
            Map.series_id == book.series_id, (Map.book_id.is_(None)) | (Map.book_id == book_id)
        )
    ):
        if m.asset_id is None:
            out.append(
                Problem(
                    "info",
                    "map_no_image",
                    f"Map '{m.title}' has no image",
                    entity_type="map",
                    entity_id=m.id,
                )
            )
        for i, mk in enumerate(m.markers):
            nid, lid = mk.get("node_id"), mk.get("lore_id")
            # Book maps link this book's sections; series maps any book's in the series.
            linkable = nodes if m.book_id == book_id else series_nodes
            broken = (nid and nid not in linkable) or (lid and session.get(LoreEntry, lid) is None)
            if broken:
                out.append(
                    Problem(
                        "warning",
                        "map_marker_broken",
                        f"Map '{m.title}': marker '{mk.get('label') or i + 1}' links to something "
                        "that was deleted",
                        entity_type="map",
                        entity_id=m.id,
                        field=f"markers[{i}]",
                    )
                )
    used = set(
        session.scalars(
            select(RefIndex.target_id).where(
                RefIndex.series_id == book.series_id, RefIndex.target_type == "asset"
            )
        )
    )
    for a in session.scalars(select(Asset).where(Asset.series_id == book.series_id)):
        if a.id not in used:
            out.append(
                Problem(
                    "info",
                    "asset_unused",
                    f"The image '{a.filename}' isn't used anywhere",
                    entity_type="asset",
                    entity_id=a.id,
                )
            )
    return out
