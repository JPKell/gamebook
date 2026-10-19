"""The standalone web player: a static, offline-capable reader for one book (SPEC §3.3, §6.2).

The export is a zip of the prebuilt player app (``frontend/dist-player``) plus:

- ``book.js`` sets ``window.GAMEBOOK``: the game bundle (versioned), approved prose,
  digital art, maps and the codex pages for every tier;
- ``images/``: the art the reader sees, scaled for screens;
- ``manifest.webmanifest``, ``sw.js`` and an icon, so served over HTTPS it installs as
  a PWA and plays offline. Opened straight from disk (``file://``) it still works.

The player runs the TypeScript engine port, proven identical to the Python engine
by the golden traces and the parity corpus.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.core.art import DigitalLayout
from gamebook.core.engine.bundle import to_bundle
from gamebook.db.models import Appendix, ArtPlacement, Asset, Book, Map, Series
from gamebook.render import appendix as render
from gamebook.schemas.art import AppendixOptions
from gamebook.services import appendix, play, snapshot
from gamebook.services.assets import Store
from gamebook.services.common import require
from gamebook.services.errors import InvalidError
from gamebook.services.printing import _screen_size

PLAYER_FORMAT = "gamebook-player"
PLAYER_VERSION = 1
#: Codex kinds that unlock entry by entry as the reader meets them.
UNLOCKED = frozenset({"bestiary", "items"})


class _Images:
    """Collects the images the player needs, scaled for screens, by stable name."""

    def __init__(self, session: Session, store: Store) -> None:
        self.session = session
        self.store = store
        self.files: dict[str, bytes] = {}

    def name(self, asset: Asset | None) -> str | None:
        if asset is None:
            return None
        name = f"images/{asset.sha256[:20]}.{asset.ext}"
        if name not in self.files:
            path = self.store.path(asset.sha256, asset.ext)
            if not path.is_file():
                return None  # missing file: the reader shows no image rather than a broken one
            self.files[name] = _screen_size(path.read_bytes(), asset.ext)
        return name

    def by_id(self, asset_id: str | None) -> str | None:
        return self.name(self.session.get(Asset, asset_id)) if asset_id else None


def player_data(session: Session, store: Store, book_id: str) -> tuple[dict[str, Any], _Images]:
    book = require(session, Book, book_id)
    series = require(session, Series, book.series_id)
    snap = snapshot.book_snapshot(session, book_id)
    if snap.rules is None:
        raise InvalidError("The series has no active rule system")
    if not snap.start_node_id:
        raise InvalidError("The book has no start section")
    images = _Images(session, store)
    variant_ids = [v.id for n in snap.nodes for v in n.variants]
    prose = play.prose_for(session, variant_ids)
    # Beat notes stand in (marked as a draft) wherever a version of a section has no prose.
    unwritten = [
        n.id for n in snap.nodes if not n.variants or not all(prose.get(v.id) for v in n.variants)
    ]
    notes = {k: v for k, v in play.beat_notes_for(session, unwritten).items() if v.strip()}

    art: dict[str, list[dict[str, Any]]] = {}
    cover = None
    rows = session.scalars(
        select(ArtPlacement)
        .where(
            ArtPlacement.book_id == book_id,
            ArtPlacement.media.in_(("digital", "both")),
            ArtPlacement.asset_id.is_not(None),
        )
        .order_by(ArtPlacement.position, ArtPlacement.created_at)
    )
    for p in rows:
        asset = session.get(Asset, p.asset_id) if p.asset_id else None
        file = images.name(asset)
        if not file or asset is None:
            continue
        digital = DigitalLayout.model_validate(p.digital or {})
        view = {
            "file": file,
            "alt": asset.alt_text,
            "caption": p.caption or asset.caption,
            "display": digital.display,
            "zoom": digital.zoom,
            "variant_id": p.variant_id,
            "tier": p.tier,
        }
        if p.target_type == "node" and p.node_id:
            art.setdefault(p.node_id, []).append(view)
        elif p.role == "cover_front" and cover is None:
            cover = {"file": file, "alt": asset.alt_text}

    maps = []
    for m in session.scalars(
        select(Map)
        .where(Map.series_id == book.series_id, (Map.book_id.is_(None)) | (Map.book_id == book_id))
        .order_by(Map.title)
    ):
        asset = session.get(Asset, m.asset_id) if m.asset_id else None
        maps.append(
            {
                "id": m.id,
                "title": m.title,
                "file": images.name(asset),
                "alt": (asset.alt_text if asset else "") or m.title,
                "markers": m.markers,
            }
        )

    tiers = [{"key": t.key, "label": t.label} for t in snap.rules.tiers]
    enabled = [
        a
        for a in session.scalars(
            select(Appendix).where(Appendix.book_id == book_id).order_by(Appendix.position)
        )
        if a.enabled and a.kind != "sheet"  # the player shows the sheet itself
    ]

    def asset_file(asset_id: str) -> str:
        return images.by_id(asset_id) or ""

    codex: dict[str, list[dict[str, Any]]] = {}
    for t in tiers:
        pages = []
        for a in enabled:
            opts = AppendixOptions.model_validate(a.options or {})
            update: dict[str, Any] = {"tier": t["key"], "blank_entries": False}
            if a.kind in UNLOCKED:
                update["spoilers"] = "all"  # the reader's own progress hides what's unmet
            if a.kind == "maps":
                continue  # the player's map panel shows the maps, with revealed markers only
            html = appendix.render_kind(
                session,
                book,
                a.kind,
                a.title,
                opts.model_copy(update=update),
                snap=snap,
                asset_url=asset_file,
            )
            # A whole document (styles included) for the player's sandboxed frame.
            pages.append(
                {
                    "id": a.id,
                    "title": a.title,
                    "kind": a.kind,
                    "html": render.document(a.title, html),
                }
            )
        codex[t["key"]] = pages

    data = {
        "format": PLAYER_FORMAT,
        "version": PLAYER_VERSION,
        "book_id": book.id,
        "title": book.title,
        "series_title": series.title,
        "tiers": tiers,
        "bundle": to_bundle(snap),
        "text": {k: v for k, v in prose.items() if v.strip()},
        "notes": notes,
        "art": art,
        "cover": cover,
        "maps": maps,
        "codex": codex,
    }
    return data, images


ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#3b2f20"/><path d="M14 16h16c3 0 2 2 2 2v32s-1-2-4-2H14zM50 16H34s-2 0-2 2v32s1-2 4-2h14z" fill="#f3e9d6"/></svg>"""


def _service_worker(files: list[str], book_id: str, version: str) -> str:
    """Cache-first offline support for the exported files (HTTPS only; file:// skips it).

    Caches are named per book, so several books on one site never delete each other's;
    files are cached one by one, so a host without a directory index ("./") still installs.
    """
    prefix = f"gamebook-{book_id}-"
    return (
        f"const PREFIX = {json.dumps(prefix)};\n"
        f"const CACHE = PREFIX + {json.dumps(version)};\n"
        f"const FILES = {json.dumps(['./', *files])};\n"
        "self.addEventListener('install', (e) => {\n"
        "  e.waitUntil(caches.open(CACHE).then((c) => Promise.allSettled(FILES.map((f) => c.add(f))))"
        ".then(() => self.skipWaiting()));\n"
        "});\n"
        "self.addEventListener('activate', (e) => {\n"
        "  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k.startsWith(PREFIX) && k !== CACHE)"
        ".map((k) => caches.delete(k)))).then(() => self.clients.claim()));\n"
        "});\n"
        "self.addEventListener('fetch', (e) => {\n"
        "  if (e.request.method !== 'GET') return;\n"
        "  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));\n"
        "});\n"
    )


def build_web(session: Session, store: Store, player_dist: Path | None, book_id: str) -> bytes:
    """The web player zip for one book."""
    if player_dist is None or not (player_dist / "player.html").is_file():
        raise InvalidError("The web player hasn't been built yet (run `make build`)")
    data, images = player_data(session, store, book_id)
    book_js = (
        "window.GAMEBOOK = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    )
    app_files: dict[str, bytes] = {}
    for path in sorted(player_dist.rglob("*")):
        if path.is_file():
            app_files[path.relative_to(player_dist).as_posix()] = path.read_bytes()
    index = app_files.pop("player.html").decode()
    # Classic scripts so the player also runs from file:// (module scripts are blocked there).
    index = index.replace('type="module"', "defer").replace(" crossorigin", "")
    index = index.replace("<!-- GAMEBOOK_TITLE -->", _escape(data["title"]))
    app_files["index.html"] = index.encode()
    manifest = {
        "name": data["title"],
        "short_name": data["title"][:12],
        "start_url": "./",
        "display": "standalone",
        "background_color": "#f6f1e7",
        "theme_color": "#3b2f20",
        "icons": [{"src": "icon.svg", "sizes": "any", "type": "image/svg+xml"}],
    }
    files: dict[str, bytes] = {
        **app_files,
        "book.js": book_js.encode(),
        "manifest.webmanifest": json.dumps(manifest, indent=1).encode(),
        "icon.svg": ICON.encode(),
        **images.files,
    }
    version = hashlib.sha256(b"".join(files[k] for k in sorted(files))).hexdigest()[:12]
    files["sw.js"] = _service_worker(sorted(files), data["book_id"], version).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            is_image = name.startswith("images/")
            info.compress_type = zipfile.ZIP_STORED if is_image else zipfile.ZIP_DEFLATED
            zf.writestr(info, files[name])
    return buf.getvalue()


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
