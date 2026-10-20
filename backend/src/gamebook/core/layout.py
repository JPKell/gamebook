"""Print layout: text styles, running heads, section spacing and signatures (SPEC §6.3a).

Pure models plus the stylesheet they produce. A book's ``PageSetup`` (``core.art``)
carries these; every field has a default, so older setups keep their look. Styles
store only what the author changed; ``effective_style`` fills in the rest from
``DEFAULT_STYLES``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


TextRole = Literal[
    "body",
    "title",
    "subtitle",
    "byline",
    "title_note",
    "act",
    "section",
    "heading",
    "subheading",
    "matter",
    "direction",
    "turn",
    "combat",
    "effects",
    "table",
    "hint",
    "ending",
    "caption",
    "header",
    "footer",
]

#: Role → (label, what it covers), in the order the designer lists them.
ROLES: dict[TextRole, tuple[str, str]] = {
    "body": ("Body text", "Section prose; other text inherits its font"),
    "title": ("Book title", "The title page"),
    "subtitle": ("Subtitle", "Under the title"),
    "byline": ("Author line", "The title page's byline"),
    "title_note": ("Series and edition", "The title page's small print"),
    "act": ("Act headings", "Act titles"),
    "section": ("Section numbers", "The number heading each section"),
    "heading": ("Matter headings", "Character, rules, sheet and appendix titles"),
    "subheading": ("Matter subheadings", "Headings inside the front and back matter"),
    "matter": ("Matter text", "Text of the front and back matter"),
    "direction": ("Page directions", "Choices, routes and 'turn to' lines"),
    "turn": ("Section references", "The numbers readers turn to"),
    "combat": ("Combat", "Enemy stat tables"),
    "effects": ("Effects", "Stat changes and other effects"),
    "table": ("Tables", "Shops and appendix tables"),
    "hint": ("Notes and hints", "Small print: tick-box notes, hints"),
    "ending": ("Endings", "The end of a path"),
    "caption": ("Captions", "Under artwork"),
    "header": ("Running header", "Top of each page"),
    "footer": ("Running footer", "Bottom of each page"),
}

#: A font family name: no quotes, semicolons or braces can reach the stylesheet.
_FONT = re.compile(r"^[\w][\w .\-]{0,79}$")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class TextStyle(_Model):
    """One text role's look; unset fields keep the default."""

    font: str | None = Field(default=None, max_length=80)
    size_pt: float | None = Field(default=None, ge=4, le=96)
    line_height: float | None = Field(default=None, ge=0.8, le=3)
    bold: bool | None = None
    italic: bool | None = None
    small_caps: bool | None = None
    case: Literal["none", "upper", "lower", "capitalize"] | None = None
    align: Literal["left", "center", "right", "justify"] | None = None
    color: str | None = None
    letter_spacing_em: float | None = Field(default=None, ge=-0.1, le=0.5)
    space_before_mm: float | None = Field(default=None, ge=0, le=80)
    space_after_mm: float | None = Field(default=None, ge=0, le=80)
    #: First-line indent (body: paragraphs after the first).
    indent_mm: float | None = Field(default=None, ge=0, le=30)

    @field_validator("font")
    @classmethod
    def _font(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        v = v.strip()
        if not _FONT.fullmatch(v):
            raise ValueError("Use a font family name: letters, digits, spaces, '.', '-', '_'")
        return v

    @field_validator("color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        if not _COLOR.fullmatch(v.strip()):
            raise ValueError("Use a colour like #1a2b3c")
        return v.strip().lower()


#: The book's look when nothing is set (the Phase 11 stylesheet's values).
DEFAULT_FONT = 'Georgia, "Iowan Old Style", "Palatino Linotype", serif'
DEFAULT_STYLES: dict[TextRole, TextStyle] = {
    "body": TextStyle(
        size_pt=10.5, line_height=1.42, align="justify", color="#111111", space_after_mm=2
    ),
    "title": TextStyle(size_pt=20, bold=True, align="center", space_after_mm=6),
    "subtitle": TextStyle(size_pt=13, italic=True, align="center", space_after_mm=4),
    "byline": TextStyle(size_pt=12, align="center", space_after_mm=4),
    "title_note": TextStyle(color="#555555", align="center"),
    "act": TextStyle(size_pt=24, bold=True, align="center", space_before_mm=40, space_after_mm=6),
    "section": TextStyle(
        size_pt=15, bold=True, align="center", space_before_mm=4, space_after_mm=2
    ),
    "heading": TextStyle(size_pt=18, bold=True, align="center", space_after_mm=6),
    "subheading": TextStyle(),
    "matter": TextStyle(),
    "direction": TextStyle(align="left"),
    "turn": TextStyle(bold=True),
    "combat": TextStyle(size_pt=9),
    "effects": TextStyle(),
    "table": TextStyle(size_pt=9),
    "hint": TextStyle(size_pt=8.5, color="#444444"),
    "ending": TextStyle(bold=True, align="center"),
    "caption": TextStyle(size_pt=8, align="center", color="#444444"),
    "header": TextStyle(size_pt=9, color="#555555"),
    "footer": TextStyle(size_pt=9, color="#555555"),
}


def effective_style(styles: Mapping[TextRole, TextStyle], role: TextRole) -> TextStyle:
    base = DEFAULT_STYLES[role]
    own = styles.get(role)
    if own is None:
        return base
    return base.model_copy(update=own.model_dump(exclude_none=True))


# ── running heads ────────────────────────────────────────────────────────

RunContent = Literal[
    "none", "page", "title", "series", "edition", "act", "section_first", "section_last", "text"
]


class RunningSlots(_Model):
    left: RunContent = "none"
    center: RunContent = "none"
    right: RunContent = "none"


class RunningLine(_Model):
    """A header or footer: what each slot shows on left (verso) and right (recto) pages."""

    verso: RunningSlots = Field(default_factory=RunningSlots)
    recto: RunningSlots = Field(default_factory=RunningSlots)
    #: For slots showing "text".
    text: str = Field(default="", max_length=120)
    #: Space between it and the text block.
    gap_mm: float = Field(default=4.0, ge=0, le=40)


def page_numbers() -> RunningLine:
    """The default footer: the page number, centred."""
    return RunningLine(verso=RunningSlots(center="page"), recto=RunningSlots(center="page"))


# ── the rest of the page ─────────────────────────────────────────────────


class TitlePage(_Model):
    subtitle: str = Field(default="", max_length=200)
    byline: str = Field(default="", max_length=200)
    show_series: bool = True
    show_edition: bool = True
    #: Space above the title.
    top_mm: float = Field(default=30.0, ge=0, le=300)


class SectionLayout(_Model):
    #: Space between sections.
    gap_mm: float = Field(default=5.0, ge=0, le=60)
    divider: Literal["none", "rule", "asterism", "fleuron"] = "none"
    #: Move a section to the next page rather than split it.
    keep_together: bool = False
    hyphenate: bool = True
    #: Where an act's heading starts: the next right-hand page, the next page, or in the flow.
    act_break: Literal["right", "page", "none"] = "right"


#: Pages per signature: 0 means one signature for the whole book (saddle stitch).
SIGNATURE_MAX = 128


class Imposition(_Model):
    """Folded sheets and signatures."""

    #: Each sheet holds two pages per side and is folded in half: the page size
    #: becomes half the sheet, and the PDF is laid out in sheets for printing.
    fold: bool = False
    sheet_width_mm: float = Field(default=279.4, ge=100, le=1200)
    sheet_height_mm: float = Field(default=215.9, ge=100, le=1200)
    #: Pages per signature (a multiple of 4). 0: unfolded, no padding; folded, one
    #: signature for the whole book.
    signature_pages: int = Field(default=0, ge=0, le=SIGNATURE_MAX)
    #: Shift inner sheets' pages towards the fold by up to this much (paper thickness).
    creep_mm: float = Field(default=0.0, ge=0, le=5)
    fold_marks: bool = True

    @field_validator("signature_pages")
    @classmethod
    def _multiple_of_four(cls, v: int) -> int:
        if v % 4:
            raise ValueError("A signature's page count must be a multiple of 4")
        return v

    def folded_page(self) -> tuple[float, float]:
        """(width, height) of a page: the sheet folded across its long side."""
        long, short = (
            max(self.sheet_width_mm, self.sheet_height_mm),
            min(self.sheet_width_mm, self.sheet_height_mm),
        )
        w, h = round(long / 2, 2), round(short, 2)
        if w > 600 or h > 900:
            raise ValueError("Folded, this sheet makes pages larger than 600 x 900 mm")
        return w, h


def padded_count(pages: int, imp: Imposition) -> int:
    """Pages after blank padding: whole signatures (folded: at least whole sheets)."""
    unit = imp.signature_pages or (4 if imp.fold else 1)
    return -(-max(pages, 1) // unit) * unit


def booklet_sides(pages: int, signature: int) -> list[tuple[int, int]]:
    """Sheet sides as (left page, right page) indices, front then back of each sheet.

    ``pages`` is already padded to whole signatures; ``signature`` is pages per
    signature (0: all of them). Sheets nest: the first sheet of a signature carries
    its first two and last two pages.
    """
    sig = signature or pages
    if pages % 4 or sig % 4 or pages % sig:
        raise ValueError("pages and signature must be multiples of 4, pages of signature")
    sides: list[tuple[int, int]] = []
    for start in range(0, pages, sig):
        for i in range(sig // 4):
            lo, hi = start + 2 * i, start + sig - 1 - 2 * i
            sides.append((hi, lo))
            sides.append((lo + 1, hi - 1))
    return sides


# ── the stylesheet ───────────────────────────────────────────────────────

#: Where each role applies. ``body`` prefixes raise them above the base stylesheet.
_SELECTORS: dict[TextRole, str] = {
    "body": ".sec p.text",
    "title": ".titlepage h1",
    "subtitle": ".titlepage .subtitle",
    "byline": ".titlepage .byline",
    "title_note": ".titlepage .series, .titlepage .edition",
    "act": "h1.act",
    "section": ".sec h2.num",
    "heading": ".matter h1",
    "subheading": ".matter h2, .matter h3",
    "matter": ".matter p, .matter li",
    "direction": ".choice p, ul.route li, ul.outcomes li, .found li",
    "turn": "a.turn",
    "combat": "table.fight th, table.fight td",
    "effects": ".effects p",
    "table": ".shop table th, .shop table td, .matter table th, .matter table td",
    "hint": ".hint",
    "ending": "p.ending",
    "caption": ".art figcaption",
}

_CASES = {"none": "none", "upper": "uppercase", "lower": "lowercase", "capitalize": "capitalize"}
_DIVIDERS = {"asterism": "* * *", "fleuron": "\\2767"}


#: CSS generic families: unquoted, or browsers take them for a font's name.
GENERIC_FAMILIES = ("serif", "sans-serif", "monospace")


def font_stack(font: str | None) -> str:
    if not font:
        return DEFAULT_FONT
    return font if font in GENERIC_FAMILIES else f'"{font}", serif'


def css_string(text: str) -> str:
    """A CSS string literal of ``text``: quotes, backslashes, ``<``, ``>`` and controls escaped."""
    out = []
    for ch in text:
        if ch in '"\\':
            out.append("\\" + ch)
        # "<" and ">" too: the stylesheet is inlined, so never "</style>".
        elif ch in "<>" or ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\{ord(ch):x} ")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _declarations(s: TextStyle, *, box: bool = False, base: TextStyle | None = None) -> list[str]:
    """CSS declarations for a style; ``box``: a page-margin box (no spacing or alignment)."""
    d: list[str] = []
    if s.font and (base is None or s.font != base.font):
        d.append(f"font-family: {font_stack(s.font)}")
    if s.size_pt is not None:
        d.append(f"font-size: {s.size_pt:g}pt")
    if s.line_height is not None:
        d.append(f"line-height: {s.line_height:g}")
    if s.bold is not None:
        d.append(f"font-weight: {'bold' if s.bold else 'normal'}")
    if s.italic is not None:
        d.append(f"font-style: {'italic' if s.italic else 'normal'}")
    if s.small_caps is not None:
        d.append(f"font-variant: {'small-caps' if s.small_caps else 'normal'}")
    if s.case is not None:
        d.append(f"text-transform: {_CASES[s.case]}")
    if s.color is not None:
        d.append(f"color: {s.color}")
    if s.letter_spacing_em is not None:
        d.append(f"letter-spacing: {s.letter_spacing_em:g}em")
    if box:
        return d
    if s.align is not None:
        d.append(f"text-align: {s.align}")
    if s.space_before_mm is not None:
        d.append(f"margin-top: {s.space_before_mm:g}mm")
    if s.space_after_mm is not None:
        d.append(f"margin-bottom: {s.space_after_mm:g}mm")
    return d


def _content(what: str, text: str) -> str | None:
    return {
        "page": "counter(page)",
        "title": "string(book-title)",
        "series": "string(series-title)",
        "edition": "string(edition)",
        "act": "string(act-title)",
        "section_first": "string(section, first)",
        "section_last": "string(section, last)",
        "text": css_string(text),
    }.get(what)


_BOXES = ("left", "center", "right")


def _running(
    line: RunningLine, slots: RunningSlots, edge: str, style: TextStyle, font: str | None
) -> list[str]:
    out = []
    pad = "padding-bottom" if edge == "top" else "padding-top"
    valign = "bottom" if edge == "top" else "top"
    look = "; ".join(
        [
            f"font-family: {font_stack(style.font or font)}",
            *_declarations(style, box=True, base=style),
        ]
    )
    for box in _BOXES:
        content = _content(getattr(slots, box), line.text)
        if content is None:
            out.append(f"@{edge}-{box} {{ content: none; }}")
        else:
            out.append(
                f"@{edge}-{box} {{ content: {content}; vertical-align: {valign}; "
                f"{pad}: {line.gap_mm:g}mm; text-align: {box}; {look} }}"
            )
    return out


def _no_running() -> str:
    return " ".join(f"@{e}-{b} {{ content: none; }}" for e in ("top", "bottom") for b in _BOXES)


def stylesheet(
    *,
    styles: Mapping[TextRole, TextStyle],
    header: RunningLine,
    footer: RunningLine,
    title_page: TitlePage,
    sections: SectionLayout,
    paged: bool,
    font_faces: str = "",
) -> str:
    """The layout's CSS, appended to the base print or proof stylesheet.

    ``paged``: print (running heads, page breaks); otherwise the scrolling proof.
    """
    out = [font_faces] if font_faces else []
    body = effective_style(styles, "body")
    base = [f"font-family: {font_stack(body.font)}"] + [
        x
        for x in _declarations(body, box=True)
        if x.startswith(("font-size", "line-height", "color"))
    ]
    out.append(f"html, body {{ {'; '.join(base)}; }}")
    for role, selector in _SELECTORS.items():
        s = effective_style(styles, role)
        decls = _declarations(s, base=body if role != "body" else None)
        if role == "body":
            # Indent paragraphs after the first, as books do.
            decls = [x for x in decls if not x.startswith("font-family")]
            if s.indent_mm:
                out.append(f"body .sec p.text + p.text {{ text-indent: {s.indent_mm:g}mm; }}")
        elif s.indent_mm:
            decls.append(f"text-indent: {s.indent_mm:g}mm")
        if decls:
            scoped = ", ".join(f"body {x.strip()}" for x in selector.split(","))
            out.append(f"{scoped} {{ {'; '.join(decls)}; }}")
    out.append("body .sec p.text.draft { font-style: italic; color: #444; }")
    out.append(f"body .titlepage {{ padding-top: {title_page.top_mm:g}mm; }}")
    out.append(f"body .sec {{ margin-bottom: {sections.gap_mm:g}mm; }}")
    out.append(f"body .sec p.text {{ hyphens: {'auto' if sections.hyphenate else 'manual'}; }}")
    if sections.divider == "rule":
        out.append(
            'body .sec + .sec::before { content: ""; display: block; width: 30%; '
            "margin: 0 auto 3mm; border-top: 0.3mm solid #999; }"
        )
    elif sections.divider in _DIVIDERS:
        out.append(
            f'body .sec + .sec::before {{ content: "{_DIVIDERS[sections.divider]}"; '
            "display: block; text-align: center; margin-bottom: 2mm; color: #777; }"
        )
    if not paged:
        return "\n".join(out)
    if sections.keep_together:
        out.append("body .sec { break-inside: avoid; }")
    act_break = {"right": "right", "page": "page", "none": "auto"}[sections.act_break]
    out.append(f"body h1.act {{ break-before: {act_break}; }}")
    # Strings for running heads (set where they appear; carried to later pages).
    out.append(".titlepage h1 { string-set: book-title content(); }")
    out.append(".titlepage .series { string-set: series-title content(); }")
    out.append(".titlepage .edition { string-set: edition content(); }")
    out.append("h1.act { string-set: act-title content(); }")
    out.append(".sec h2.num { string-set: section content(); }")
    head, foot = effective_style(styles, "header"), effective_style(styles, "footer")
    for side, which in (("left", "verso"), ("right", "recto")):
        boxes = _running(header, getattr(header, which), "top", head, body.font)
        boxes += _running(footer, getattr(footer, which), "bottom", foot, body.font)
        out.append(f"@page :{side} {{ {' '.join(boxes)} }}")
    # No running heads on the title page, art pages, blank pages or the first page.
    out.append(".titlepage, .begin, .artpage { page: plain; }")
    for sel in ("@page plain", "@page full", "@page :blank", "@page :first"):
        out.append(f"{sel} {{ {_no_running()} }}")
    return "\n".join(out)
