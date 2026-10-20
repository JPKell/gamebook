"""Print layout: styles, the stylesheet, running heads and signature arithmetic."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gamebook.core.art import PageSetup
from gamebook.core.layout import (
    DEFAULT_STYLES,
    ROLES,
    Imposition,
    RunningLine,
    RunningSlots,
    SectionLayout,
    TextStyle,
    TitlePage,
    booklet_sides,
    css_string,
    effective_style,
    padded_count,
    stylesheet,
)


def sheet(**kw: object) -> str:
    args: dict[str, object] = {
        "styles": {},
        "header": RunningLine(),
        "footer": RunningLine(),
        "title_page": TitlePage(),
        "sections": SectionLayout(),
        "paged": True,
        **kw,
    }
    return stylesheet(**args)  # type: ignore[arg-type]


def test_every_role_has_a_label_and_default() -> None:
    assert set(ROLES) == set(DEFAULT_STYLES)


def test_effective_style_overlays_only_what_was_set() -> None:
    s = effective_style({"section": TextStyle(size_pt=22, italic=True)}, "section")
    assert (s.size_pt, s.italic, s.bold, s.align) == (22, True, True, "center")
    assert effective_style({}, "hint") == DEFAULT_STYLES["hint"]


@pytest.mark.parametrize("font", ['Evil"; } body { x', "a{b}", "x;y", "'quoted'"])
def test_font_names_cannot_escape_the_stylesheet(font: str) -> None:
    with pytest.raises(ValidationError):
        TextStyle(font=font)


@pytest.mark.parametrize("color", ["red", "#fff", "#12345g", "url(x)"])
def test_colours_are_hex(color: str) -> None:
    with pytest.raises(ValidationError):
        TextStyle(color=color)


def test_blank_font_and_colour_mean_default() -> None:
    assert TextStyle(font="  ", color="").model_dump(exclude_none=True) == {}
    assert TextStyle(color="#AABBCC").color == "#aabbcc"


def test_css_string_escapes() -> None:
    assert css_string('a"b\\c\nd') == '"a\\"b\\\\c\\a d"'


def test_stylesheet_applies_roles() -> None:
    css = sheet(
        styles={
            "body": TextStyle(font="DejaVu Serif", size_pt=11, indent_mm=4),
            "section": TextStyle(font="DejaVu Sans", case="upper", letter_spacing_em=0.1),
            "combat": TextStyle(color="#aa0000"),
        }
    )
    assert 'html, body { font-family: "DejaVu Serif", serif; font-size: 11pt;' in css
    assert "body .sec p.text + p.text { text-indent: 4mm; }" in css
    section = next(line for line in css.splitlines() if line.startswith("body .sec h2.num {"))
    assert 'font-family: "DejaVu Sans", serif' in section
    assert "text-transform: uppercase" in section
    assert "letter-spacing: 0.1em" in section
    assert "color: #aa0000" in css


def test_running_heads_and_their_strings() -> None:
    css = sheet(
        header=RunningLine(
            verso=RunningSlots(left="section_first", right="title"),
            recto=RunningSlots(left="text", right="section_last"),
            text='Say "hi"',
            gap_mm=6,
        ),
        footer=RunningLine(verso=RunningSlots(left="page"), recto=RunningSlots(right="page")),
    )
    left = next(line for line in css.splitlines() if line.startswith("@page :left"))
    right = next(line for line in css.splitlines() if line.startswith("@page :right"))
    assert "@top-left { content: string(section, first);" in left
    assert "@top-right { content: string(book-title);" in left
    assert "padding-bottom: 6mm" in left
    assert '@top-left { content: "Say \\"hi\\"";' in right
    assert "@top-right { content: string(section, last);" in right
    assert "@bottom-right { content: counter(page);" in right
    assert "@bottom-center { content: none; }" in right
    assert ".sec h2.num { string-set: section content(); }" in css
    # No running heads on the title page, art pages or blank pages.
    assert "@page plain {" in css
    assert "@page :blank {" in css


def test_the_proof_gets_styles_but_no_paging() -> None:
    css = sheet(paged=False, sections=SectionLayout(divider="fleuron", keep_together=True))
    assert "@page" not in css
    assert "string-set" not in css
    assert "break-inside" not in css  # paged only
    assert '"\\2767"' in css


def test_section_options() -> None:
    css = sheet(sections=SectionLayout(gap_mm=8, keep_together=True, hyphenate=False))
    assert "body .sec { margin-bottom: 8mm; }" in css
    assert "body .sec { break-inside: avoid; }" in css
    assert "hyphens: manual" in css
    assert "body h1.act { break-before: auto; }" in sheet(sections=SectionLayout(act_break="none"))


def test_title_page_padding() -> None:
    assert "body .titlepage { padding-top: 55mm; }" in sheet(title_page=TitlePage(top_mm=55))


# ── page setup ────────────────────────────────────────────────────────────


def test_gutter_narrows_the_text_block() -> None:
    plain = PageSetup()
    bound = PageSetup(gutter_mm=6)
    assert bound.inner_mm == plain.margin_inner_mm + 6
    assert bound.text_width_mm == pytest.approx(plain.text_width_mm - 6)


def test_folded_sheets_set_the_page_size() -> None:
    letter = PageSetup(
        imposition=Imposition(fold=True, sheet_width_mm=215.9, sheet_height_mm=279.4)
    )
    assert (letter.trim_width_mm, letter.trim_height_mm) == (139.7, 215.9)
    a4 = PageSetup(
        trim_width_mm=100,
        imposition=Imposition(fold=True, sheet_width_mm=297, sheet_height_mm=210),
    )
    assert (a4.trim_width_mm, a4.trim_height_mm) == (148.5, 210)


def test_old_setups_still_load() -> None:
    s = PageSetup.model_validate({"trim_width_mm": 140, "margin_inner_mm": 20})
    assert s.footer.verso.center == "page"
    assert s.header.verso.center == "none"
    assert s.styles == {}
    assert not s.imposition.fold


@pytest.mark.parametrize("pages", [3, 6, 130])
def test_signatures_must_be_multiples_of_four(pages: int) -> None:
    with pytest.raises(ValidationError):
        Imposition(signature_pages=pages)


# ── signatures ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("pages", "fold", "sig", "want"),
    [
        (10, False, 0, 10),
        (10, False, 8, 16),
        (10, True, 0, 12),
        (10, True, 8, 16),
        (16, True, 16, 16),
        (0, True, 0, 4),
    ],
)
def test_padded_count(pages: int, fold: bool, sig: int, want: int) -> None:
    assert padded_count(pages, Imposition(fold=fold, signature_pages=sig)) == want


def test_a_single_sheet() -> None:
    # Back cover | front cover; inside: page 2 | page 3.
    assert booklet_sides(4, 0) == [(3, 0), (1, 2)]


def test_one_signature_nests_its_sheets() -> None:
    assert booklet_sides(8, 0) == [(7, 0), (1, 6), (5, 2), (3, 4)]


def test_signatures_are_folded_separately() -> None:
    assert booklet_sides(8, 4) == [(3, 0), (1, 2), (7, 4), (5, 6)]


def test_every_page_lands_once() -> None:
    sides = booklet_sides(32, 8)
    placed = [p for side in sides for p in side]
    assert sorted(placed) == list(range(32))
    # Facing pages on a side always add up to the signature's ends.
    for k, (left, right) in enumerate(sides):
        start = (k // 4) * 8
        assert left + right == 2 * start + 7


def test_booklet_sides_rejects_partial_signatures() -> None:
    with pytest.raises(ValueError, match="multiples"):
        booklet_sides(12, 8)


# ── review regressions ────────────────────────────────────────────────────


def test_custom_text_cannot_close_the_style_element() -> None:
    assert css_string("</style>") == '"\\3c /style\\3e "'
    css = sheet(header=RunningLine(verso=RunningSlots(left="text"), text="</style><b>hi</b>"))
    assert "<" not in css
    assert ">" not in css


def test_defaults_keep_the_phase_11_look() -> None:
    css = sheet()
    assert ".begin" not in css.split("body h1.act")[0]  # "begin" keeps its centring
    assert ".draft-note" not in css
    assert "body .matter h2" not in css  # subheadings keep the appendix styles


def test_generic_families_are_not_quoted() -> None:
    css = sheet(styles={"section": TextStyle(font="sans-serif")})
    assert "font-family: sans-serif;" in css
    assert '"sans-serif"' not in css


def test_unknown_roles_are_dropped() -> None:
    s = PageSetup.model_validate({"styles": {"body": {"size_pt": 12}, "future_role": {}}})
    assert set(s.styles) == {"body"}


def test_folding_a_huge_sheet_is_rejected() -> None:
    with pytest.raises(ValidationError, match="600 x 900"):
        PageSetup(imposition=Imposition(fold=True, sheet_width_mm=1200, sheet_height_mm=1000))
