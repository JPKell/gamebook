"""Print editions: numbering, compiling, the proof, PDF and EPUB (SPEC §6.3, ADR 0012).

One edition per tier. The compiled sections (``core.printbook``) are laid out with
the book's page setup and each placement's print controls, framed by front matter
(cover, title page, character creation, rules, adventure sheet) and back matter (the
book's enabled appendices).
"""

from __future__ import annotations

import io
import random
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from markupsafe import Markup
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.core.art import DigitalLayout, PageSetup, PrintLayout, print_size
from gamebook.core.gbx.scope import RefKind
from gamebook.core.model import BookSnapshot
from gamebook.core.printbook import compile as pc
from gamebook.core.printbook import numbering
from gamebook.core.printbook.verify import VerifyReport, verify
from gamebook.core.rules.schema import effective_tier
from gamebook.db.models import Appendix, ArtPlacement, Asset, Book, Job, Series
from gamebook.jobs import JobContext
from gamebook.render import print as render
from gamebook.render.appendix import _env
from gamebook.schemas.art import AppendixOptions
from gamebook.services import appendix, art, play, snapshot
from gamebook.services.assets import Store
from gamebook.services.common import require
from gamebook.services.errors import InvalidError

#: Sections per EPUB file (e-readers slow down on very long documents).
EPUB_CHUNK = 40
#: Images are scaled to fit this for e-readers.
EPUB_MAX_PX = 1600

# ── numbering ───────────────────────────────────────────────────────────


def _numbering(session: Session, book: Book, snap: BookSnapshot) -> numbering.Numbering:
    """Number the sections, keeping last time's numbers; the map is saved when it changes."""
    result = numbering.assign(
        pc.section_keys(snap),
        seed=book.print_seed,
        pins=pc.pins(snap),
        previous=book.print_numbers or {},
    )
    if result.numbers != (book.print_numbers or {}):
        book.print_numbers = result.numbers
        session.flush()
    return result


def reshuffle(session: Session, book_id: str, seed: int | None = None) -> int:
    """Renumber every section (pins stay); returns the new seed."""
    book = require(session, Book, book_id)
    book.print_seed = seed if seed is not None else random.SystemRandom().randint(1, 2**31 - 1)
    book.print_numbers = {}
    session.flush()
    _numbering(session, book, snapshot.book_snapshot(session, book_id))
    return book.print_seed


@dataclass
class Compiled:
    book: Book
    snap: BookSnapshot
    printed: pc.PrintBook
    ignored_pins: dict[str, int]


def _tier(snap: BookSnapshot, tier: str | None) -> str:
    if snap.rules is None:
        raise InvalidError("The series has no active rule system")
    keys = snap.rules.tier_keys()
    if tier is None:
        return keys[-1]
    if tier not in keys:
        raise InvalidError(f"Unknown tier {tier!r}", field="tier")
    return tier


def compile_book(session: Session, book_id: str, tier: str | None) -> Compiled:
    book = require(session, Book, book_id)
    snap = snapshot.book_snapshot(session, book_id)
    t = _tier(snap, tier)
    if not snap.nodes:
        raise InvalidError("The book has no sections yet")
    nums = _numbering(session, book, snap)
    prose = play.prose_for(session, [v.id for n in snap.nodes for v in n.variants])
    notes = play.beat_notes_for(session, [n.id for n in snap.nodes])
    printed = pc.compile_book(snap, t, nums.numbers, prose=prose, notes=notes)
    return Compiled(book, snap, printed, nums.ignored_pins)


# ── art ─────────────────────────────────────────────────────────────────


def _art_views(
    session: Session,
    book: Book,
    tier: str,
    media: str,
    asset_url: Callable[[Asset], str],
) -> list[dict[str, Any]]:
    """Placements of this book for one medium and tier, ready for the templates."""
    setup = art.page_setup(book)
    rows = list(
        session.scalars(
            select(ArtPlacement)
            .where(
                ArtPlacement.book_id == book.id,
                ArtPlacement.target_type.in_(("node", "act", "book")),
                ArtPlacement.media.in_((media, "both")),
                (ArtPlacement.tier.is_(None)) | (ArtPlacement.tier == tier),
            )
            .order_by(ArtPlacement.position, ArtPlacement.created_at)
        )
    )
    assets = {
        a.id: a
        for a in session.scalars(
            select(Asset).where(Asset.id.in_({p.asset_id for p in rows if p.asset_id}))
        )
    }
    out = []
    for p in rows:
        layout = PrintLayout.model_validate(p.layout or {})
        asset = assets.get(p.asset_id or "")
        size = print_size(
            layout, setup, asset.width_px if asset else None, asset.height_px if asset else None
        )
        page_side = layout.page_side
        if layout.position == "facing_page":
            page_side = "verso"
        out.append(
            {
                "id": p.id,
                "role": p.role,
                "node_id": p.node_id,
                "act_id": p.act_id,
                "variant_id": p.variant_id,
                "url": asset_url(asset) if asset else None,
                "alt": (asset.alt_text if asset else "") or "",
                "caption": p.caption or (asset.caption if asset else ""),
                "brief": p.brief,
                "size": layout.size,
                "bleed": layout.size == "full_page" and layout.bleed,
                "width_mm": size.width_mm,
                "height_mm": size.height_mm,
                "align": layout.align,
                "wrap": layout.wrap and layout.size in ("half", "third", "vignette", "custom"),
                "gutter_mm": layout.gutter_mm,
                "focal_x": layout.focal_x,
                "focal_y": layout.focal_y,
                "position": layout.position,
                "paragraph": layout.paragraph,
                "page_side": page_side,
                "keep_with": layout.keep_with,
                "digital": DigitalLayout.model_validate(p.digital or {}).model_dump(),
            }
        )
    return out


# ── parts ───────────────────────────────────────────────────────────────


@dataclass
class Parts:
    title: str
    series_title: str
    tier_label: str
    setup: PageSetup
    parts: list[dict[str, Any]] = field(default_factory=list)


def _creation(c: Compiled) -> Markup:
    assert c.snap.rules is not None
    t = effective_tier(c.snap.rules, c.printed.tier)
    names = {
        RefKind.STAT: {k: s.label for k, s in t.stats.items()},
        RefKind.SKILL: {k: s.label for k, s in t.skills.items()},
    }

    def namer(kind: RefKind, key: str) -> str:
        return names.get(kind, {}).get(key, key)

    from gamebook.core import gbx

    def english(src: str) -> str:
        try:
            return gbx.number_to_english(gbx.parse(src), namer, tiers=c.snap.rules.tier_keys())  # type: ignore[union-attr]
        except Exception:
            return src

    stats = [
        {"label": s.label, "initial": english(s.initial), "has_max": s.max_is_initial}
        for s in t.stats.values()
        if "player" in s.applies_to
    ]
    classes = [
        {
            "label": cl.label,
            "description": cl.description,
            "skills": [names[RefKind.SKILL].get(k, k) for k in cl.skills],
        }
        for cl in t.classes.values()
    ]
    currency = next((s.label for s in t.stats.values() if s.kind == "resource"), None)
    html = (
        _env()
        .get_template("print/creation.html")
        .render(
            stats=stats,
            classes=classes,
            skills=[s.label for s in t.skills.values()],
            currency=currency,
        )
    )
    return Markup(html)


def build_parts(
    session: Session,
    c: Compiled,
    *,
    media: str,
    asset_url: Callable[[Asset], str],
) -> Parts:
    """Front matter, sections (with their art and act openers) and back matter, in order."""
    book, snap, printed = c.book, c.snap, c.printed
    series = require(session, Series, book.series_id)
    out = Parts(book.title, series.title, printed.tier_label, art.page_setup(book))
    views = _art_views(session, book, printed.tier, media, asset_url)

    def by_role(role: str) -> list[dict[str, Any]]:
        return [v for v in views if v["role"] == role]

    def url_for_id(asset_id: str) -> str:
        a = session.get(Asset, asset_id)
        return asset_url(a) if a else ""

    # Front matter
    for v in by_role("cover_front"):
        out.parts.append({"kind": "art", "art": {**v, "anchor": f"art-{v['id']}"}})
    for v in by_role("endpaper"):
        out.parts.append({"kind": "art", "art": {**v, "anchor": f"art-{v['id']}"}})
    for v in by_role("frontispiece"):
        out.parts.append(
            {"kind": "art", "art": {**v, "page_side": "verso", "anchor": f"art-{v['id']}"}}
        )
    title_art = by_role("title_page")
    out.parts.append(
        {
            "kind": "title",
            "art": {**title_art[0], "anchor": f"art-{title_art[0]['id']}"} if title_art else None,
        }
    )
    enabled = [
        a
        for a in session.scalars(
            select(Appendix).where(Appendix.book_id == book.id).order_by(Appendix.position)
        )
        if a.enabled
    ]
    kinds = {a.kind for a in enabled}

    def fragment(kind: str, title: str, opts: AppendixOptions) -> Markup:
        opts = opts.model_copy(update={"tier": printed.tier})  # the edition's tier, always
        return Markup(
            appendix.render_kind(session, book, kind, title, opts, snap=snap, asset_url=url_for_id)
        )

    out.parts.append({"kind": "html", "cls": "creation", "html": _creation(c)})
    if "rules" not in kinds:
        out.parts.append(
            {
                "kind": "html",
                "cls": "rules",
                "html": fragment("rules", "How to Play", AppendixOptions()),
            }
        )
    if "sheet" not in kinds:
        out.parts.append(
            {
                "kind": "html",
                "cls": "sheet",
                "html": fragment("sheet", "Adventure Sheet", AppendixOptions()),
            }
        )
    out.parts.append({"kind": "begin", "n": printed.start or 1})

    # Sections, with act openers before each act's first section
    acts = {a.id: a for a in snap.acts}
    act_index = {a.id: i for i, a in enumerate(sorted(snap.acts, key=lambda a: a.position))}
    openers = {v["act_id"]: v for v in by_role("opener")}
    node_art: dict[str, list[dict[str, Any]]] = {}
    for v in by_role("illustration"):
        node_art.setdefault(v["node_id"], []).append(v)
    current_act = None
    for s in printed.sections:
        if s.act_id != current_act and len(acts) > 1:
            current_act = s.act_id
            opener = openers.get(s.act_id)
            out.parts.append(
                {
                    "kind": "act",
                    "index": act_index.get(s.act_id, 0),
                    "title": acts[s.act_id].title if s.act_id in acts else "",
                    "art": {**opener, "anchor": f"art-{opener['id']}"} if opener else None,
                }
            )
        out.parts.append({"kind": "section", "section": _section_view(s, node_art)})

    # Back matter
    for a in enabled:
        opts = AppendixOptions.model_validate(a.options or {})
        out.parts.append(
            {"kind": "html", "cls": f"appendix-{a.kind}", "html": fragment(a.kind, a.title, opts)}
        )
    for v in by_role("cover_back"):
        out.parts.append(
            {"kind": "art", "art": {**v, "page_side": "verso", "anchor": f"art-{v['id']}"}}
        )
    return out


def _section_view(s: pc.Section, node_art: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    paragraphs = [p.strip() for p in s.text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    before: list[dict[str, Any]] = []
    after: list[dict[str, Any]] = []
    own: list[dict[str, Any]] = []
    after_para: dict[int, list[dict[str, Any]]] = {}
    if s.kind != "router":
        for v in node_art.get(s.node_id, []):
            if v["variant_id"] and v["variant_id"] != s.variant_id:
                continue
            v = {**v, "anchor": f"art-{v['id']}-{s.number}"}
            if v["size"] == "full_page" or v["position"] in ("own_page", "facing_page"):
                own.append(v)
            elif v["position"] == "before_text":
                before.append(v)
            elif v["position"] == "after_paragraph" and v["paragraph"] <= len(paragraphs):
                after_para.setdefault(v["paragraph"], []).append(v)
            else:
                after.append(v)
    return {
        "number": s.number,
        "kind": s.kind,
        "ticks": s.ticks,
        "tick_note": s.tick_note,
        "draft": s.draft,
        "paragraphs": paragraphs,
        "blocks": s.blocks,
        "art_before": before,
        "art_after": after,
        "art_after_para": after_para,
        "art_own": own,
    }


# ── outputs ─────────────────────────────────────────────────────────────


def preview_html(session: Session, book_id: str, tier: str | None) -> str:
    """The proof: the whole edition as one page, for an iframe."""
    c = compile_book(session, book_id, tier)
    parts = build_parts(session, c, media="print", asset_url=lambda a: f"/api/assets/{a.id}/thumb")
    return render.document(
        title=parts.title,
        series_title=parts.series_title,
        tier_label=parts.tier_label,
        parts=parts.parts,
        mode="screen",
        setup=parts.setup,
    )


@dataclass
class LayoutWarning:
    code: str
    message: str
    number: int | None = None


def pdf(
    session: Session, store: Store, book_id: str, tier: str | None
) -> tuple[bytes, int, list[LayoutWarning]]:
    """(PDF bytes, page count, layout warnings). Images load from the asset store only."""
    from weasyprint import HTML, URLFetcher  # heavy import: only when printing

    c = compile_book(session, book_id, tier)
    root = store.root.resolve()

    def file_url(a: Asset) -> str:
        return store.path(a.sha256, a.ext).resolve().as_uri()

    parts = build_parts(session, c, media="print", asset_url=file_url)
    html = render.document(
        title=parts.title,
        series_title=parts.series_title,
        tier_label=parts.tier_label,
        parts=parts.parts,
        mode="print",
        setup=parts.setup,
        marks=True,
    )

    class StoreOnly(URLFetcher):  # type: ignore[misc]
        """Only our own image files: no network, no other local files."""

        def fetch(self, url: str, headers: Any = None) -> Any:
            if url.startswith("file://"):
                path = Path(unquote(url[len("file://") :].split("?")[0])).resolve()
                if path.is_relative_to(root) and path.is_file():
                    return super().fetch(url, headers)
            raise ValueError(f"Blocked resource: {url}")

    fetcher = StoreOnly(allowed_protocols={"file"})
    document = HTML(string=html, url_fetcher=fetcher, base_url=root.as_uri() + "/").render()
    warnings = _layout_warnings(document, parts)
    return document.write_pdf(), len(document.pages), warnings


def _layout_warnings(document: Any, parts: Parts) -> list[LayoutWarning]:
    """Keep-with: each section's art must land on the same spread as its number."""
    page_of: dict[str, int] = {}
    for i, page in enumerate(document.pages):
        for name in page.anchors:
            page_of.setdefault(name, i)

    def spread(i: int) -> int:  # page 1 stands alone (recto); then 2-3, 4-5...
        return (i + 1) // 2

    out: list[LayoutWarning] = []
    for part in parts.parts:
        if part["kind"] != "section":
            continue
        s = part["section"]
        at = page_of.get(f"s{s['number']}")
        if at is None:
            continue
        arts = [*s["art_before"], *s["art_after"], *s["art_own"]]
        arts += [a for group in s["art_after_para"].values() for a in group]
        for a in arts:
            got = page_of.get(a["anchor"])
            if got is None:
                continue
            if a["position"] == "facing_page" and not (got % 2 == 1 and at == got + 1):
                out.append(
                    LayoutWarning(
                        "art_not_facing",
                        f"The art for section {s['number']} isn't on the page facing it "
                        f"(art on page {got + 1}, section on page {at + 1})",
                        s["number"],
                    )
                )
            elif a["keep_with"] and spread(got) != spread(at):
                out.append(
                    LayoutWarning(
                        "art_separated",
                        f"The art for section {s['number']} lands on page {got + 1}, away from "
                        f"its section on page {at + 1}",
                        s["number"],
                    )
                )
    return out


def epub(session: Session, store: Store, book_id: str, tier: str | None) -> bytes:
    """An EPUB 3 with internal links, the digital art (scaled for screens) and a nav."""
    c = compile_book(session, book_id, tier)
    images: dict[str, tuple[str, bytes]] = {}

    def image_url(a: Asset) -> str:
        name = f"images/{a.sha256[:20]}.{a.ext}"
        if name not in images:
            path = store.path(a.sha256, a.ext)
            data = path.read_bytes() if path.is_file() else b""
            images[name] = (a.mime, _screen_size(data, a.ext) if data else b"")
        # A missing file prints as a placeholder rather than a broken link.
        return name if images[name][1] else ""

    parts = build_parts(session, c, media="digital", asset_url=image_url)
    book, printed = c.book, c.printed
    # Split: front matter, sections in chunks, back matter.
    docs: list[tuple[str, list[dict[str, Any]]]] = []
    front: list[dict[str, Any]] = []
    back: list[dict[str, Any]] = []
    body: list[list[dict[str, Any]]] = [[]]
    seen_section = False
    for p in parts.parts:
        if p["kind"] in ("section", "act"):
            seen_section = True
            if (
                p["kind"] == "section"
                and len([x for x in body[-1] if x["kind"] == "section"]) >= EPUB_CHUNK
            ):
                body.append([])
            body[-1].append(p)
        elif not seen_section:
            front.append(p)
        else:
            back.append(p)
    docs.append(("front.xhtml", front))
    file_of: dict[int, str] = {}
    for i, chunk in enumerate(body, start=1):
        name = f"sections-{i:03d}.xhtml"
        docs.append((name, chunk))
        for p in chunk:
            if p["kind"] == "section":
                file_of[p["section"]["number"]] = name
    if back:
        docs.append(("back.xhtml", back))

    def href(n: int) -> str:
        return f"{file_of.get(n, 'front.xhtml')}#s{n}"

    xhtml = {
        name: _to_xhtml(
            render.document(
                title=parts.title,
                series_title=parts.series_title,
                tier_label=parts.tier_label,
                parts=chunk,
                mode="epub",
                setup=parts.setup,
                href=href,
                css_href="style.css",
            )
        )
        for name, chunk in docs
    }
    nav_items = [("front.xhtml", "Start")]
    for name, chunk in docs[1:]:
        acts = [p for p in chunk if p["kind"] == "act"]
        nums = [p["section"]["number"] for p in chunk if p["kind"] == "section"]
        if name == "back.xhtml":
            nav_items.append((name, "Appendices"))
        elif acts:
            nav_items += [(f"{name}#act-{a['index']}", a["title"]) for a in acts]
        elif nums:
            nav_items.append((name, f"Sections {nums[0]}-{nums[-1]}"))
    return _epub_zip(
        # One identifier per edition: e-readers must not merge the tiers' books.
        identifier=f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'gamebook:{book.id}:{printed.tier}')}",
        title=f"{book.title} ({printed.tier_label})",
        modified=(book.updated_at or book.created_at).strftime("%Y-%m-%dT%H:%M:%SZ"),
        css=render.css("epub", parts.setup),
        docs=xhtml,
        images={k: v for k, v in images.items() if v[1]},
        nav=nav_items,
    )


def _screen_size(data: bytes, ext: str) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        if max(im.size) <= EPUB_MAX_PX:
            return data
        im.thumbnail((EPUB_MAX_PX, EPUB_MAX_PX))
        out = io.BytesIO()
        fmt = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}[ext]
        (im.convert("RGB") if fmt == "JPEG" else im).save(out, fmt, quality=85)
        return out.getvalue()


XHTML_NS = "http://www.w3.org/1999/xhtml"


def _to_xhtml(html: str) -> str:
    """HTML → well-formed XHTML (e-readers parse strictly)."""
    import tinyhtml5

    root = tinyhtml5.parse(html)
    ET.register_namespace("", XHTML_NS)
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n' + body


def _epub_zip(
    *,
    identifier: str,
    title: str,
    modified: str,
    css: str,
    docs: dict[str, str],
    images: dict[str, tuple[str, bytes]],
    nav: list[tuple[str, str]],
) -> bytes:
    from xml.sax.saxutils import escape, quoteattr

    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
    ]
    manifest.append('<item id="css" href="style.css" media-type="text/css"/>')
    spine = []
    for i, name in enumerate(docs):
        manifest.append(f'<item id="d{i}" href="{name}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="d{i}"/>')
    for i, (name, (mime, _)) in enumerate(sorted(images.items())):
        manifest.append(f'<item id="i{i}" href="{name}" media-type="{mime}"/>')
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="en">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{escape(identifier)}</dc:identifier>
    <dc:title>{escape(title)}</dc:title>
    <dc:language>en</dc:language>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    {chr(10).join("    " + m for m in manifest).strip()}
  </manifest>
  <spine>
    {chr(10).join("    " + s for s in spine).strip()}
  </spine>
</package>
"""
    items = "\n".join(
        f"<li><a href={quoteattr(href)}>{escape(label)}</a></li>" for href, label in nav
    )
    nav_doc = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">
<head><title>{escape(title)}</title></head>
<body><nav epub:type="toc" id="toc"><h1>Contents</h1><ol>
{items}
</ol></nav></body></html>
"""
    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:

        def put(name: str, data: str | bytes, *, store_only: bool = False) -> None:
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED if store_only else zipfile.ZIP_DEFLATED
            zf.writestr(info, data)

        put("mimetype", "application/epub+zip", store_only=True)  # must be first, uncompressed
        put("META-INF/container.xml", container)
        put("OEBPS/content.opf", opf)
        put("OEBPS/nav.xhtml", nav_doc)
        put("OEBPS/style.css", css)
        for name, doc in docs.items():
            put(f"OEBPS/{name}", doc)
        for name, (_, data) in sorted(images.items()):
            put(f"OEBPS/{name}", data, store_only=True)
    return buf.getvalue()


# ── checks ──────────────────────────────────────────────────────────────


def preflight(session: Session, book_id: str, tier: str | None) -> dict[str, Any]:
    """Everything worth fixing before printing this edition."""
    c = compile_book(session, book_id, tier)
    art_problems = [
        p
        for p in art.problems(session, book_id)
        if p.code in ("art_low_dpi", "art_bleed", "art_placeholder", "art_alt_text")
    ]
    printed = c.printed
    by_node = {n.id: n for n in c.snap.nodes}
    pins_ignored = []
    for key, n in c.ignored_pins.items():
        node = by_node.get(key.split(":", 1)[1])
        pins_ignored.append(
            {
                "node_id": node.id if node else None,
                "message": f"{node.title if node else key}: pin {n} is outside its act's numbers or taken",
            }
        )
    return {
        "tier": printed.tier,
        "tier_label": printed.tier_label,
        "seed": c.book.print_seed,
        "sections": len(printed.sections),
        "routers": sum(s.kind == "router" for s in printed.sections),
        "tick_boxes": sum(s.ticks for s in printed.sections),
        "drafts": sum(s.draft for s in printed.sections),
        "warnings": [
            {"code": w.code, "message": w.message, "node_id": w.node_id, "number": w.number}
            for w in printed.warnings
        ]
        + [{"code": "pin_ignored", **p, "number": None} for p in pins_ignored],
        "art": [
            {
                "code": p.code,
                "severity": p.severity,
                "message": p.message,
                "node_id": p.node_id,
            }
            for p in art_problems
        ],
        "numbers": [
            {"number": s.number, "node_id": s.node_id, "title": s.title, "kind": s.kind}
            for s in printed.sections
        ],
    }


def verify_book(session: Session, book_id: str, tier: str | None, runs: int) -> VerifyReport:
    c = compile_book(session, book_id, tier)
    return verify(c.snap, c.printed, runs=runs)


# ── export jobs ─────────────────────────────────────────────────────────


def exports_dir(data_dir: Path) -> Path:
    return data_dir / "exports"


def start_export(session: Session, book_id: str, tier: str | None, fmt: str) -> Job:
    """A job that builds the PDF or EPUB (the file lands in ``data_dir/exports``)."""
    book = require(session, Book, book_id)
    snap = snapshot.book_snapshot(session, book_id)
    t = _tier(snap, tier)
    job = Job(
        kind=f"print_{fmt}",
        label=f"{fmt.upper()}: {book.title} ({t})",
        total=1,
        payload={"book_id": book_id, "tier": t, "format": fmt},
    )
    session.add(job)
    session.flush()
    return job


def export_job(book_id: str, tier: str, fmt: str, store: Store, folder: Path) -> Any:
    def run(ctx: JobContext) -> dict[str, Any]:
        with ctx.db.session() as s:
            book = require(s, Book, book_id)
            name = f"{book.key}-{tier}.{fmt}"
            if fmt == "pdf":
                data, pages, warnings = pdf(s, store, book_id, tier)
                extra: dict[str, Any] = {
                    "pages": pages,
                    "warnings": [w.__dict__ for w in warnings],
                }
            else:
                data, extra = epub(s, store, book_id, tier), {}
        ctx.check()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{ctx.job_id}.{fmt}").write_bytes(data)
        _prune(folder)
        ctx.progress(1, 1, force=True)
        return {"file": name, "format": fmt, "bytes": len(data), **extra}

    return run


#: Finished exports kept on disk (older ones are deleted; build again to re-download).
KEEP_EXPORTS = 20


def _prune(folder: Path) -> None:
    files = sorted(
        (p for p in folder.iterdir() if p.suffix in (".pdf", ".epub")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in files[KEEP_EXPORTS:]:
        old.unlink(missing_ok=True)


def export_file(session: Session, folder: Path, job_id: str) -> tuple[Path, str, str]:
    """(path, download name, media type) of a finished export."""
    job = require(session, Job, job_id)
    fmt = (job.payload or {}).get("format")
    if not job.kind.startswith("print_") or fmt not in ("pdf", "epub"):
        raise InvalidError("That job isn't a print export")
    if job.status != "done" or not job.result:
        raise InvalidError("The export isn't finished")
    path = folder / f"{job.id}.{fmt}"
    if not path.is_file():
        raise InvalidError("The export file is gone; export again")
    media = "application/pdf" if fmt == "pdf" else "application/epub+zip"
    return path, str(job.result.get("file", path.name)), media
