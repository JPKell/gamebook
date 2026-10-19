"""Print geometry for artwork, and the safe Markdown subset for author pages."""

from __future__ import annotations

import pytest

from gamebook.core.art import (
    PageSetup,
    PrintLayout,
    crop_box,
    crop_px,
    default_layout,
    pixels_needed,
    print_size,
)
from gamebook.render.markdown import to_html

PAGE = PageSetup()  # 6x9 in, 117.4 x 188.6 mm text block


def test_text_block() -> None:
    assert PAGE.text_width_mm == pytest.approx(117.4)
    assert PAGE.text_height_mm == pytest.approx(188.6)


def test_dpi_drops_as_the_print_grows() -> None:
    sizes = ["vignette", "third", "half", "full_width"]
    dpis = [
        print_size(PrintLayout.model_validate({"size": s}), PAGE, 1200, 900).dpi or 0 for s in sizes
    ]
    assert dpis == sorted(dpis, reverse=True)
    half = print_size(PrintLayout(size="half"), PAGE, 1200, 900)
    assert (half.width_mm, half.dpi, half.status) == (58.7, 519, "good")
    full = print_size(PrintLayout(size="full_width"), PAGE, 1200, 900)
    assert full.status == "low"  # 260 dpi
    assert print_size(PrintLayout(size="full_width"), PAGE, 500, 400).status == "poor"


def test_max_height_and_tall_images_fit_the_box() -> None:
    tall = print_size(PrintLayout(size="full_width"), PAGE, 1000, 4000)
    assert tall.height_mm == pytest.approx(PAGE.text_height_mm, abs=0.1)
    assert tall.width_mm < PAGE.text_width_mm
    capped = print_size(PrintLayout(size="full_width", max_height_mm=50), PAGE, 3000, 2000)
    assert capped.height_mm == 50
    assert capped.dpi == round(2000 / (50 / 25.4))


def test_custom_width() -> None:
    assert print_size(PrintLayout(size="custom", width_mm=80), PAGE, 3000, 3000).width_mm == 80
    pct = print_size(PrintLayout(size="custom", width_pct=25), PAGE, 3000, 3000)
    assert pct.width_mm == pytest.approx(117.4 / 4, abs=0.1)


def test_full_bleed_covers_trim_plus_bleed() -> None:
    layout = PrintLayout(size="full_page", bleed=True)
    s = print_size(layout, PAGE, 2000, 1000)  # landscape art on a portrait page: cropped
    assert (s.width_mm, s.height_mm) == (round(152.4 + 3.175, 1), round(228.6 + 6.35, 1))
    assert s.dpi == round(1000 / ((228.6 + 6.35) / 25.4))  # height-limited
    w, h = pixels_needed(layout, PAGE)
    assert (w, h) == (round(155.575 / 25.4 * 300), round(234.95 / 25.4 * 300))


def test_crop() -> None:
    assert crop_px(1600, 900, PrintLayout(aspect="1:1")) == (900, 900)
    w, h = crop_px(900, 1600, PrintLayout(aspect="16:9"))
    assert w == 900
    assert h == pytest.approx(506.25)
    # The focal point moves the crop but never past the edges.
    assert crop_box(1600, 900, PrintLayout(aspect="1:1", focal_x=0)) == (0, 0, 900, 900)
    assert crop_box(1600, 900, PrintLayout(aspect="1:1", focal_x=1)) == (700, 0, 1600, 900)
    assert crop_box(1600, 900, PrintLayout(aspect="1:1")) == (350, 0, 1250, 900)
    # A square crop keeps fewer pixels at the same printed width: lower DPI.
    square = print_size(PrintLayout(size="half", aspect="1:1"), PAGE, 1600, 900).dpi or 0
    assert square < (print_size(PrintLayout(size="half"), PAGE, 1600, 900).dpi or 0)


def test_placeholders_and_role_defaults() -> None:
    s = print_size(PrintLayout(size="half"), PAGE, None, None)
    assert (s.dpi, s.status) == (None, "none")
    assert s.height_mm == pytest.approx(58.7 * 3 / 4, abs=0.1)
    assert default_layout("opener").page_side == "recto"
    assert default_layout("cover_front").bleed is True
    assert default_layout("portrait").wrap is True


def test_markdown_is_escaped_and_small() -> None:
    out = to_html(
        "# Title\n\nSome **bold** and *it* <b>raw</b>\nnext line\n\n- a\n- [[mara]]\n\n1. one\n\n---",
        lambda kind, key: "Mara the Witch" if key == "mara" else None,
    )
    assert "<h2>Title</h2>" in out
    assert "<strong>bold</strong> and <em>it</em> &lt;b&gt;raw&lt;/b&gt; next line" in out
    assert '<ul>\n<li>a</li>\n<li><span class="mention">Mara the Witch</span></li>\n</ul>' in out
    assert "<ol>\n<li>one</li>\n</ol>" in out
    assert out.endswith("<hr>")
    assert "[[x|Shown]]" not in to_html("[[x|Shown]]")
    assert '"' not in to_html('a "quoted" <tag onload="x">').replace("&#34;", "")
