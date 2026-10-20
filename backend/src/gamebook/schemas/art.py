"""Artwork schemas: assets, placements, page setup, maps and appendices (SPEC §2.13-2.14)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from gamebook.core.art import DigitalLayout, PageSetup, PrintLayout
from gamebook.core.layout import TextStyle
from gamebook.schemas.common import In, Key, Out, Title

TargetType = Literal["node", "act", "book", "character", "enemy", "item", "lore"]
Role = Literal[
    "illustration",
    "opener",
    "cover_front",
    "cover_back",
    "frontispiece",
    "title_page",
    "endpaper",
    "portrait",
    "image",
]
#: The roles each kind of target can have.
ROLES_FOR: dict[str, tuple[str, ...]] = {
    "node": ("illustration",),
    "act": ("opener",),
    "book": ("cover_front", "cover_back", "frontispiece", "title_page", "endpaper"),
    "character": ("portrait", "image"),
    "enemy": ("portrait", "image"),
    "item": ("portrait", "image"),
    "lore": ("portrait", "image"),
}
Status = Literal["needed", "sketch", "final"]
Media = Literal["print", "digital", "both"]

# ── assets ────────────────────────────────────────────────────────────────


class AssetOut(Out):
    id: str
    series_id: str
    sha256: str
    filename: str
    mime: str
    width_px: int
    height_px: int
    bytes: int
    alt_text: str
    caption: str
    credit: str
    licence: str
    tags: list[str]
    created_at: datetime
    #: How many placements and maps use it.
    uses: int = 0
    url: str
    thumb_url: str


class AssetUploadOut(AssetOut):
    #: False when the same image was already in the library.
    created: bool = True


class AssetUpdate(In):
    filename: str | None = Field(default=None, min_length=1, max_length=255)
    alt_text: str | None = Field(default=None, max_length=2000)
    caption: str | None = Field(default=None, max_length=2000)
    credit: str | None = Field(default=None, max_length=300)
    licence: str | None = Field(default=None, max_length=200)
    tags: list[str] | None = Field(default=None, max_length=50)


class AssetUse(Out):
    kind: Literal["placement", "map"]
    id: str
    role: str
    target_type: str
    label: str
    book_id: str | None = None
    book_title: str | None = None
    node_id: str | None = None


# ── placements ────────────────────────────────────────────────────────────


class ArtPlacementIn(In):
    target_type: TargetType
    target_id: str
    role: Role | None = None
    asset_id: str | None = None
    variant_id: str | None = None
    tier: str | None = Field(default=None, max_length=64)
    media: Media = "both"
    caption: str = Field(default="", max_length=2000)
    brief: str = Field(default="", max_length=4000)
    status: Status | None = None
    layout: PrintLayout | None = None
    digital: DigitalLayout | None = None

    @model_validator(mode="after")
    def _role(self) -> ArtPlacementIn:
        allowed = ROLES_FOR[self.target_type]
        if self.role is None:
            self.role = allowed[0]  # type: ignore[assignment]
        elif self.role not in allowed:
            raise ValueError(
                f"A {self.target_type} can't have a {self.role} (use {', '.join(allowed)})"
            )
        if self.variant_id and self.target_type != "node":
            raise ValueError("Only node illustrations can be limited to a text variant")
        return self


class ArtPlacementUpdate(In):
    role: Role | None = None
    #: Null makes it a placeholder; omit to keep the image.
    asset_id: str | None = None
    variant_id: str | None = None
    tier: str | None = Field(default=None, max_length=64)
    media: Media | None = None
    caption: str | None = Field(default=None, max_length=2000)
    brief: str | None = Field(default=None, max_length=4000)
    status: Status | None = None
    layout: PrintLayout | None = None
    digital: DigitalLayout | None = None


class PrintSizeOut(Out):
    width_mm: float
    height_mm: float
    dpi: float | None
    #: good | low | poor | none
    status: str
    box_width_mm: float
    box_height_mm: float
    #: Pixels for 300 DPI at this size.
    needed_px: tuple[int, int]


class ArtPlacementOut(Out):
    id: str
    series_id: str
    target_type: str
    target_id: str
    target_label: str
    book_id: str | None
    node_id: str | None
    act_id: str | None
    role: str
    asset_id: str | None
    asset: AssetOut | None
    variant_id: str | None
    tier: str | None
    media: str
    position: int
    caption: str
    brief: str
    status: str
    layout: PrintLayout
    digital: DigitalLayout
    print_size: PrintSizeOut
    created_at: datetime


# ── page setup ────────────────────────────────────────────────────────────


class RoleOut(Out):
    key: str
    label: str
    description: str
    default: TextStyle


class PageSetupOut(PageSetup):
    text_width: float = 0
    text_height: float = 0
    #: Text roles in display order, with their defaults (``styles`` holds only changes).
    roles: list[RoleOut] = Field(default_factory=list)


# ── maps ──────────────────────────────────────────────────────────────────


class Marker(In):
    id: str = Field(min_length=1, max_length=40)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    label: str = Field(default="", max_length=200)
    node_id: str | None = None
    lore_id: str | None = None
    #: gbx condition: only shown to readers for whom it holds (e.g. a codeword).
    visible_if: str | None = Field(default=None, max_length=500)


class MapIn(In):
    title: Title
    key: Key | None = None
    book_id: str | None = None
    asset_id: str | None = None


class MapUpdate(In):
    title: Title | None = None
    #: Null makes it a series-wide map (its markers may link sections in any book).
    book_id: str | None = None
    key: Key | None = None
    asset_id: str | None = None
    markers: list[Marker] | None = Field(default=None, max_length=500)


class MapOut(Out):
    id: str
    series_id: str
    book_id: str | None
    key: str
    title: str
    asset_id: str | None
    asset: AssetOut | None
    markers: list[dict[str, object]]


# ── appendices ────────────────────────────────────────────────────────────

AppendixKind = Literal[
    "bestiary", "sheet", "items", "rules", "personae", "glossary", "maps", "custom"
]


class AppendixOptions(In):
    #: Edition tier (None: the highest).
    tier: str | None = None
    #: all | met_on_canonical_path (only what a reader meets on the main path)
    spoilers: Literal["all", "met_on_canonical_path"] = "all"
    hide_key_items: bool = False
    #: Names with blank stat boxes for the reader to fill in.
    blank_entries: bool = False
    #: Bestiary and items: alphabetical or by first appearance in canonical order.
    order: Literal["alpha", "first_appearance"] = "alpha"
    #: Bestiary: one stat block per level used, or a table of every level used.
    stat_mode: Literal["levels", "table"] = "levels"
    show_images: bool = True
    #: Custom pages: Markdown with [[mentions]].
    body: str = Field(default="", max_length=50_000)
    #: Maps appendix: which maps (empty: all the book can use).
    map_ids: list[str] = Field(default_factory=list)
    #: Adventure sheet: inventory lines and codeword boxes.
    inventory_lines: int = Field(default=12, ge=0, le=60)
    codewords: Literal["list", "blank"] = "list"


class AppendixIn(In):
    kind: AppendixKind
    title: Title | None = None
    options: AppendixOptions = Field(default_factory=AppendixOptions)


class AppendixUpdate(In):
    title: Title | None = None
    enabled: bool | None = None
    options: AppendixOptions | None = None


class AppendixOut(Out):
    id: str
    book_id: str
    kind: str
    title: str
    position: int
    enabled: bool
    options: AppendixOptions


class RenderOut(Out):
    title: str
    #: An HTML fragment (escaped server-side) for the preview, print and the codex.
    html: str


class CodexIn(In):
    tier: str
    #: What the reader has met so far (from the player).
    enemies: list[str] = Field(default_factory=list, max_length=2000)
    items: list[str] = Field(default_factory=list, max_length=2000)
    flags: list[str] = Field(default_factory=list, max_length=2000)


# ── commissioning ─────────────────────────────────────────────────────────


class ShotRow(Out):
    placement_id: str
    book_id: str | None
    book_title: str | None
    target_type: str
    target_label: str
    role: str
    status: str
    brief: str
    has_asset: bool
    width_mm: float
    height_mm: float
    needed_px: tuple[int, int]
    node_id: str | None
