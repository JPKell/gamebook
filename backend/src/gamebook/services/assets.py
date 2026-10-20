"""The asset library: content-addressed image files, metadata, where-used and GC.

Files live at ``<data_dir>/assets/<sha256>.<ext>`` with a WebP thumbnail at
``assets/thumbs/<sha256>.webp``. Rows are per series; identical uploads to a
series are one asset. A file is removed only when no asset row — in the live
database *or in any checkpoint* — still names its hash, so restoring a
checkpoint never finds its images gone.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import logging
import os
import re
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.db.models import ArtPlacement, Asset, Map, RefIndex, Series
from gamebook.db.session import Database
from gamebook.schemas.art import AssetUpdate, AssetUse
from gamebook.services import checkpoints, refs
from gamebook.services.common import require
from gamebook.services.errors import ConflictError, InvalidError

#: Upload cap (a 600 dpi full-page bleed scan is well under this).
MAX_BYTES = 40 * 1024 * 1024
#: Refuse images over 160 Mpx (checked explicitly: Pillow itself only errors at twice its
#: limit), so a tiny compressed bomb can't make the thumbnailer decode gigabytes.
MAX_PIXELS = 160_000_000
#: Files touched this recently are never collected (an upload may be reusing one).
GC_GRACE_S = 15 * 60
THUMB_PX = 480
FORMATS = {
    "PNG": ("png", "image/png"),
    "JPEG": ("jpg", "image/jpeg"),
    "WEBP": ("webp", "image/webp"),
}
MIMES = dict(FORMATS.values())

# Our explicit check (``probe``) rejects first; Pillow's own guard is the backstop.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS * 2
log = logging.getLogger(__name__)
_SHA = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class Store:
    """Where asset files live (``<data_dir>/assets``)."""

    root: Path

    def path(self, sha: str, ext: str) -> Path:
        return self.root / f"{sha}.{ext}"

    def thumb(self, sha: str) -> Path:
        return self.root / "thumbs" / f"{sha}.webp"

    def write(self, sha: str, ext: str, data: bytes) -> None:
        """Store a file (and its thumbnail) once; atomic, so a crash never leaves half a file.

        The thumbnail is made first, so an image that can't be decoded never leaves its
        file behind. Reusing an existing file refreshes its mtime, which keeps GC (with
        its grace period) from collecting it while the new row is being committed.
        """
        if not _SHA.fullmatch(sha) or ext not in MIMES:
            raise InvalidError("Bad asset name")
        target = self.path(sha, ext)
        thumb = self.thumb(sha)
        thumb_bytes = None if thumb.exists() else _thumbnail(data)
        self.root.mkdir(parents=True, exist_ok=True)
        if target.exists():
            os.utime(target)
        else:
            _atomic_write(target, data)
        if thumb_bytes is not None:
            thumb.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(thumb, thumb_bytes)

    def read(self, sha: str, ext: str) -> bytes:
        return self.path(sha, ext).read_bytes()


def _atomic_write(target: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".upload-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _thumbnail(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as src:
        im: Image.Image = ImageOps.exif_transpose(src)  # match how browsers show it
        im.thumbnail((THUMB_PX, THUMB_PX))
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        out = io.BytesIO()
        im.save(out, "WEBP", quality=80)
        return out.getvalue()


@dataclass(frozen=True)
class Probed:
    sha256: str
    ext: str
    mime: str
    width_px: int
    height_px: int


def probe(data: bytes) -> Probed:
    """Check an upload is a PNG, JPEG or WebP image we can read; raise InvalidError if not."""
    if not data:
        raise InvalidError("The file is empty")
    if len(data) > MAX_BYTES:
        raise InvalidError(f"Images are limited to {MAX_BYTES // (1024 * 1024)} MB")
    try:
        with Image.open(io.BytesIO(data)) as im:
            fmt = im.format or ""
            if im.size[0] * im.size[1] > MAX_PIXELS:
                raise InvalidError("The image has too many pixels")
            im.verify()  # structure (cheap) ...
        # Importing WeasyPrint turns this on for the whole process; uploads must be whole.
        ImageFile.LOAD_TRUNCATED_IMAGES = False
        with Image.open(io.BytesIO(data)) as im:
            im.load()  # ... and every pixel decodes (verify misses truncated JPEGs)
            # EXIF orientation: browsers rotate the image, so sizes must match what they show.
            width, height = ImageOps.exif_transpose(im).size
    except Image.DecompressionBombError as exc:
        raise InvalidError("The image has too many pixels") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise InvalidError("Not a readable PNG, JPEG or WebP image") from exc
    if fmt not in FORMATS:
        raise InvalidError(f"{fmt or 'That'} images aren't supported; use PNG, JPEG or WebP")
    ext, mime = FORMATS[fmt]
    return Probed(hashlib.sha256(data).hexdigest(), ext, mime, width, height)


def import_blob(store: Store, sha: str, ext: str, data: bytes | None) -> Probed | None:
    """For imports: check and store one image; with no bytes, use the stored file if any.

    Returns the image's real type and size (never trusted from the archive's YAML), or
    None when there's no file for it. Raises InvalidError for a bad image.
    """
    if not _SHA.fullmatch(sha) or ext not in MIMES:
        raise InvalidError(f"assets.yaml names an invalid file {sha!r}.{ext!r}")
    if data is None:
        path = store.path(sha, ext)
        if not path.is_file():
            return None
        data = path.read_bytes()
    p = probe(data)
    if p.sha256 != sha:
        raise InvalidError(f"assets/{sha}.{ext} doesn't match its hash")
    if p.ext != ext:
        raise InvalidError(f"assets/{sha}.{ext} is really a {p.ext.upper()} image")
    store.write(sha, ext, data)
    return p


def upload(
    session: Session, store: Store, series_id: str, filename: str, data: bytes
) -> tuple[Asset, bool]:
    """Add an image to a series' library; returns (asset, created). A duplicate returns the
    existing asset."""
    require(session, Series, series_id)
    p = probe(data)
    existing = session.scalar(
        select(Asset).where(Asset.series_id == series_id, Asset.sha256 == p.sha256)
    )
    if existing is not None:
        store.write(p.sha256, p.ext, data)  # heal a missing file
        return existing, False
    store.write(p.sha256, p.ext, data)
    name = Path(filename or "image").name[:255] or "image"
    asset = Asset(
        series_id=series_id,
        sha256=p.sha256,
        ext=p.ext,
        mime=p.mime,
        filename=name,
        width_px=p.width_px,
        height_px=p.height_px,
        bytes=len(data),
        alt_text="",
        tags=[],
    )
    session.add(asset)
    session.flush()
    return asset, True


def update(session: Session, asset_id: str, data: AssetUpdate) -> Asset:
    asset = require(session, Asset, asset_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        if k == "tags" and v is not None:
            v = sorted({t.strip() for t in v if t.strip()})
        if v is not None:
            setattr(asset, k, v)
    session.flush()
    return asset


def list_assets(session: Session, series_id: str) -> list[Asset]:
    require(session, Series, series_id)
    return list(
        session.scalars(
            select(Asset).where(Asset.series_id == series_id).order_by(Asset.created_at.desc())
        )
    )


def use_counts(session: Session, series_id: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for (target,) in session.execute(
        select(RefIndex.target_id).where(
            RefIndex.series_id == series_id, RefIndex.target_type == "asset"
        )
    ):
        if target:
            out[target] = out.get(target, 0) + 1
    return out


def where_used(session: Session, asset_id: str) -> list[AssetUse]:
    """Every placement and map using an asset (from the RefIndex)."""
    asset = require(session, Asset, asset_id)
    rows = refs.where_used_detailed(session, asset.series_id, "asset", asset_id)
    placements = {
        p.id: p
        for p in session.scalars(
            select(ArtPlacement).where(
                ArtPlacement.id.in_(
                    [r.source_id for r, _, _ in rows if r.source_type == "placement"]
                )
            )
        )
    }
    maps = {
        m.id: m
        for m in session.scalars(
            select(Map).where(
                Map.id.in_([r.source_id for r, _, _ in rows if r.source_type == "map"])
            )
        )
    }
    from gamebook.services import art  # local: art imports assets

    out = []
    for r, node_title, book_title in rows:
        if r.source_type == "placement" and r.source_id in placements:
            pl = placements[r.source_id]
            out.append(
                AssetUse(
                    kind="placement",
                    id=pl.id,
                    role=pl.role,
                    target_type=pl.target_type,
                    label=art.target_label(session, pl, node_title),
                    book_id=pl.book_id,
                    book_title=book_title,
                    node_id=pl.node_id,
                )
            )
        elif r.source_type == "map" and r.source_id in maps:
            mp = maps[r.source_id]
            out.append(
                AssetUse(
                    kind="map",
                    id=mp.id,
                    role="map",
                    target_type="map",
                    label=f"Map: {mp.title}",
                    book_id=mp.book_id,
                    book_title=book_title,
                )
            )
    return out


def delete(session: Session, db: Database, store: Store, asset_id: str, *, force: bool) -> None:
    """Delete an asset row; in-use assets need ``force`` (their placements become
    placeholders, maps lose their image). Files are garbage-collected afterwards."""
    asset = require(session, Asset, asset_id)
    used = where_used(session, asset_id)
    if used and not force:
        raise ConflictError(
            f"{asset.filename} is used in {len(used)} place(s); delete with force to remove anyway",
            ref_count=len(used),
        )
    sources = [(u.kind, u.id) for u in used]
    session.delete(asset)
    session.flush()
    ctx = refs.RefContext(session, asset.series_id)
    for kind, source_id in sources:  # their asset_id is now NULL
        src = session.get(ArtPlacement if kind == "placement" else Map, source_id)
        if src is not None:
            session.refresh(src)
            refs.reindex(session, "placement" if kind == "placement" else "map", src, ctx)


def referenced_hashes(session: Session, db: Database) -> set[str]:
    """Hashes named by any asset row, live or in a checkpoint."""
    live = set(session.scalars(select(Asset.sha256)))
    try:
        cps = checkpoints.list_all(db)
        folder = checkpoints.checkpoint_dir(db)
    except InvalidError:  # in-memory database: no checkpoints
        return live
    for cp in cps:
        path = folder / f"{cp.id}.db"
        try:
            with contextlib.closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as con:
                live.update(r[0] for r in con.execute("SELECT sha256 FROM asset"))
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc):  # a checkpoint from before Phase 10
                continue
            # Unreadable (locked, half-written, corrupt): we can't tell what it needs.
            raise ConflictError(
                f"Checkpoint {cp.name!r} couldn't be read; nothing was collected"
            ) from exc
        except sqlite3.Error as exc:
            raise ConflictError(
                f"Checkpoint {cp.name!r} couldn't be read; nothing was collected"
            ) from exc
    return live


def collect_garbage(session: Session, db: Database, store: Store) -> int:
    """Remove files no row (live or checkpointed) refers to. Returns how many went."""
    if not store.root.is_dir():
        return 0
    keep = referenced_hashes(session, db)
    cutoff = time.time() - GC_GRACE_S
    removed = 0
    for path in [*store.root.glob("*.*"), *store.root.glob("thumbs/*.webp")]:
        if path.name.startswith(".") or not path.is_file() or path.stem in keep:
            continue
        # Recently written or reused files may belong to an upload not yet committed.
        family = [path, *store.root.glob(f"{path.stem}.*")]
        if any(p.stat().st_mtime > cutoff for p in family if p.exists()):
            continue
        path.unlink(missing_ok=True)
        removed += path.parent == store.root
    return removed


def collect_quietly(session: Session, db: Database, store: Store) -> None:
    """GC after a delete or import: if a checkpoint can't be read, keep everything."""
    try:
        collect_garbage(session, db, store)
    except ConflictError:
        log.warning("Asset GC skipped", exc_info=True)


def file_for(session: Session, store: Store, asset_id: str, *, thumb: bool) -> tuple[Path, str]:
    asset = require(session, Asset, asset_id)
    if not _SHA.fullmatch(asset.sha256) or asset.ext not in MIMES:
        raise InvalidError("This asset's file name is invalid")
    if thumb:
        path = store.thumb(asset.sha256)
        if not path.exists() and store.path(asset.sha256, asset.ext).exists():
            store.write(asset.sha256, asset.ext, store.read(asset.sha256, asset.ext))
        return path, "image/webp"
    # The type comes from the extension we chose, never from stored (importable) text.
    return store.path(asset.sha256, asset.ext), MIMES[asset.ext]


def asset_out(a: Asset, uses: int = 0) -> dict[str, Any]:
    return {
        "id": a.id,
        "series_id": a.series_id,
        "sha256": a.sha256,
        "filename": a.filename,
        "mime": a.mime,
        "width_px": a.width_px,
        "height_px": a.height_px,
        "bytes": a.bytes,
        "alt_text": a.alt_text,
        "caption": a.caption,
        "credit": a.credit,
        "licence": a.licence,
        "tags": a.tags,
        "created_at": a.created_at,
        "uses": uses,
        "url": f"/api/assets/{a.id}/file",
        "thumb_url": f"/api/assets/{a.id}/thumb",
    }
