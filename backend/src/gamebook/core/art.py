"""Print geometry for artwork: page setup, layout controls and effective DPI (SPEC §2.13).

Pure functions over millimetres and pixels. The printed size of a placement comes
from its size preset (relative to the page's text block), any custom width, the
maximum height, and the crop. Effective DPI is pixels per printed inch of the
cropped image, so enlarging a placement lowers it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MM_PER_INCH = 25.4
#: Below this, print artwork looks soft (warning); below ``DPI_MIN`` it fails (error).
DPI_GOOD = 300
DPI_MIN = 150
#: A vignette is a small spot illustration (SPEC: about 25-35 mm).
VIGNETTE_MM = 30.0

Size = Literal["full_page", "full_width", "half", "third", "vignette", "custom"]
Position = Literal["before_text", "after_text", "after_paragraph", "own_page", "facing_page"]
Aspect = Literal["original", "1:1", "4:3", "3:2", "2:3", "16:9"]
ASPECTS: dict[str, float] = {"1:1": 1.0, "4:3": 4 / 3, "3:2": 1.5, "2:3": 2 / 3, "16:9": 16 / 9}


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class PageSetup(_Model):
    """A book's printed page in mm. Defaults: 6x9 in trade paperback, 1/8 in bleed."""

    trim_width_mm: float = Field(default=152.4, ge=50, le=600)
    trim_height_mm: float = Field(default=228.6, ge=50, le=900)
    margin_inner_mm: float = Field(default=19.0, ge=0, le=100)
    margin_outer_mm: float = Field(default=16.0, ge=0, le=100)
    margin_top_mm: float = Field(default=18.0, ge=0, le=100)
    margin_bottom_mm: float = Field(default=22.0, ge=0, le=100)
    bleed_mm: float = Field(default=3.175, ge=0, le=20)

    @property
    def text_width_mm(self) -> float:
        return max(10.0, self.trim_width_mm - self.margin_inner_mm - self.margin_outer_mm)

    @property
    def text_height_mm(self) -> float:
        return max(10.0, self.trim_height_mm - self.margin_top_mm - self.margin_bottom_mm)


class PrintLayout(_Model):
    """Per-placement print controls (all optional; defaults suit a node illustration)."""

    size: Size = "half"
    #: full_page only: run off the trim edges (needs art covering trim + bleed).
    bleed: bool = False
    #: custom only: a width in mm, else a percentage of the text block.
    width_mm: float | None = Field(default=None, gt=0, le=600)
    width_pct: float | None = Field(default=None, gt=0, le=100)
    max_height_mm: float | None = Field(default=None, gt=0, le=900)
    position: Position = "before_text"
    #: after_paragraph only (1-based).
    paragraph: int = Field(default=1, ge=1, le=999)
    page_side: Literal["any", "recto", "verso"] = "any"
    align: Literal["left", "right", "center"] = "center"
    #: half, third and vignette only: text flows around the image.
    wrap: bool = False
    gutter_mm: float = Field(default=4.0, ge=0, le=30)
    #: Crop focal point (0-1) and aspect; the original file is never changed.
    focal_x: float = Field(default=0.5, ge=0, le=1)
    focal_y: float = Field(default=0.5, ge=0, le=1)
    aspect: Aspect = "original"
    #: Keep on the same spread as its section number.
    keep_with: bool = True


class DigitalLayout(_Model):
    display: Literal["full_width", "inline", "thumbnail"] = "inline"
    #: Tapping opens the full-size image.
    zoom: bool = True


#: Defaults per role: act openers and book art are full pages (openers recto).
ROLE_DEFAULTS: dict[str, dict[str, object]] = {
    "illustration": {},
    "opener": {"size": "full_page", "position": "own_page", "page_side": "recto"},
    "cover_front": {"size": "full_page", "bleed": True, "position": "own_page"},
    "cover_back": {"size": "full_page", "bleed": True, "position": "own_page"},
    "frontispiece": {"size": "full_page", "position": "own_page", "page_side": "verso"},
    "title_page": {"size": "full_page", "position": "own_page", "page_side": "recto"},
    "endpaper": {"size": "full_page", "bleed": True, "position": "own_page"},
    "portrait": {"size": "third", "align": "right", "wrap": True},
    "image": {"size": "half"},
}


def default_layout(role: str) -> PrintLayout:
    return PrintLayout.model_validate(ROLE_DEFAULTS.get(role, {}))


def crop_px(width_px: int, height_px: int, layout: PrintLayout) -> tuple[float, float]:
    """The pixel size of the crop (the largest box of the aspect inside the image)."""
    if layout.aspect == "original" or width_px <= 0 or height_px <= 0:
        return float(width_px), float(height_px)
    ratio = ASPECTS[layout.aspect]
    if width_px / height_px > ratio:  # too wide: trim the sides
        return height_px * ratio, float(height_px)
    return float(width_px), width_px / ratio


def crop_box(width_px: int, height_px: int, layout: PrintLayout) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the crop, centred on the focal point within bounds."""
    cw, ch = crop_px(width_px, height_px, layout)
    left = min(max(0.0, layout.focal_x * width_px - cw / 2), width_px - cw)
    top = min(max(0.0, layout.focal_y * height_px - ch / 2), height_px - ch)
    return round(left), round(top), round(left + cw), round(top + ch)


@dataclass(frozen=True)
class PrintSize:
    width_mm: float
    height_mm: float
    #: Effective DPI of the image at this size (None for a placeholder).
    dpi: float | None
    #: good | low | poor | none (placeholder)
    status: str
    #: The box it is laid out in (the page with bleed for full-bleed art).
    box_width_mm: float
    box_height_mm: float


def _box(layout: PrintLayout, page: PageSetup) -> tuple[float, float, bool]:
    """(width, height, cover?) of the area the art fills, in mm."""
    tw, th = page.text_width_mm, page.text_height_mm
    match layout.size:
        case "full_page":
            if layout.bleed:  # trim plus bleed on the three outer edges
                return (
                    page.trim_width_mm + page.bleed_mm,
                    page.trim_height_mm + 2 * page.bleed_mm,
                    True,
                )
            return tw, th, False
        case "full_width":
            return tw, th, False
        case "half":
            return tw / 2, th, False
        case "third":
            return tw / 3, th, False
        case "vignette":
            return VIGNETTE_MM, VIGNETTE_MM * 1.5, False
        case _:  # custom
            if layout.width_mm:
                w = min(layout.width_mm, page.trim_width_mm + page.bleed_mm)
            else:
                w = tw * (layout.width_pct or 50) / 100
            return w, th, False


def print_size(
    layout: PrintLayout, page: PageSetup, width_px: int | None, height_px: int | None
) -> PrintSize:
    """Printed size and effective DPI of an image (or placeholder) under a layout.

    Images fill their box's width (shrinking to fit its height and ``max_height_mm``);
    full-bleed art covers the box, so the crop may lose an edge.
    """
    bw, bh, cover = _box(layout, page)
    if layout.max_height_mm:
        bh = min(bh, layout.max_height_mm)
    if not width_px or not height_px:
        ratio = ASPECTS.get(layout.aspect, 4 / 3)
        w = bw if cover else min(bw, bh * ratio)
        h = bh if cover else w / ratio
        return PrintSize(round(w, 1), round(h, 1), None, "none", round(bw, 1), round(bh, 1))
    cw, ch = crop_px(width_px, height_px, layout)
    if cover:
        mm_per_px = max(bw / cw, bh / ch)
        w, h = bw, bh
    else:
        mm_per_px = min(bw / cw, bh / ch)
        w, h = cw * mm_per_px, ch * mm_per_px
    dpi = MM_PER_INCH / mm_per_px
    status = "good" if dpi >= DPI_GOOD else "low" if dpi >= DPI_MIN else "poor"
    return PrintSize(round(w, 1), round(h, 1), round(dpi), status, round(bw, 1), round(bh, 1))


def pixels_needed(layout: PrintLayout, page: PageSetup) -> tuple[int, int]:
    """Pixels for 300 DPI at the layout's box size (for the shot list)."""
    bw, bh, cover = _box(layout, page)
    if layout.max_height_mm:
        bh = min(bh, layout.max_height_mm)
    if not cover:  # the crop's aspect, else a 4:3 landscape box (as placeholders show)
        bh = min(bh, bw / ASPECTS.get(layout.aspect, 4 / 3))
    px = DPI_GOOD / MM_PER_INCH
    return round(bw * px), round(bh * px)
