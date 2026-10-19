from typing import Literal

from pydantic import Field, model_validator

from gamebook.core.effects import Effect
from gamebook.core.model import ChoiceKind, EndingGrade, EndingKind
from gamebook.schemas.common import In, Key, Out, Title


class LinkFrom(In):
    """Create a goto choice on ``node_id`` pointing at the new node."""

    node_id: str
    label: str = ""


class NodeCreate(In):
    act_id: str
    title: Title = "Untitled"
    key: Key | None = None
    beat_notes: str = ""
    x: float = 0.0
    y: float = 0.0
    link_from: LinkFrom | None = None


class NodeUpdate(In):
    title: Title | None = None
    key: Key | None = None
    act_id: str | None = None
    beat_notes: str | None = None
    summary: str | None = None
    is_act_entry: bool | None = None
    is_act_exit: bool | None = None
    ending_kind: EndingKind | None = None
    ending_grade: EndingGrade | None = None
    ending_label: str | None = None
    location_id: str | None = None
    canonical_predecessor_id: str | None = None
    style_override: dict[str, object] | None = None
    section_pin: int | None = Field(default=None, ge=1)
    on_enter: list[Effect] | None = None
    x: float | None = None
    y: float | None = None
    collapsed: bool | None = None
    character_ids: list[str] | None = None


class NodePosition(In):
    id: str
    x: float
    y: float


class LayoutUpdate(In):
    positions: list[NodePosition]


class DuplicateRequest(In):
    node_ids: list[str] = Field(min_length=1)
    offset_x: float = 40.0
    offset_y: float = 40.0


class DuplicateResult(Out):
    #: old node id → new node id
    mapping: dict[str, str]


# ── variants ─────────────────────────────────────────────────────────────


class VariantIn(In):
    label: Title = "Default"
    condition: str | None = None
    priority: int = 0


class VariantUpdate(In):
    label: Title | None = None
    condition: str | None = None
    priority: int | None = None


class VariantOut(Out):
    id: str
    position: int
    label: str
    condition: str | None
    priority: int


# ── choices ──────────────────────────────────────────────────────────────


class OutcomeIn(In):
    key: Key = "default"
    target_node_id: str | None = None
    range_lo: int | None = None
    range_hi: int | None = None


class OutcomeOut(Out):
    id: str
    position: int
    key: str
    target_node_id: str | None
    range_lo: int | None
    range_hi: int | None


UnmetDisplay = Literal["hide", "show_disabled"]


class ChoiceCreate(In):
    label: str = ""
    kind: ChoiceKind = "goto"
    #: Shortcut for goto choices: the destination.
    target_node_id: str | None = None
    condition: str | None = None
    unmet_display: UnmetDisplay = "hide"
    print_text: str | None = None
    min_tier: str | None = None
    effects: list[Effect] = Field(default_factory=list)
    dice: str | None = None
    test: str | None = None
    encounter_id: str | None = None
    flee_allowed: bool = False
    #: Omit to get the default outcomes for ``kind``.
    outcomes: list[OutcomeIn] | None = None

    @model_validator(mode="after")
    def _target_only_for_goto(self) -> "ChoiceCreate":
        if self.target_node_id is not None and self.outcomes is not None:
            raise ValueError("Give either target_node_id or outcomes, not both")
        return self


class ChoiceUpdate(In):
    label: str | None = None
    kind: ChoiceKind | None = None
    condition: str | None = None
    unmet_display: UnmetDisplay | None = None
    print_text: str | None = None
    min_tier: str | None = None
    effects: list[Effect] | None = None
    dice: str | None = None
    test: str | None = None
    encounter_id: str | None = None
    flee_allowed: bool | None = None
    outcomes: list[OutcomeIn] | None = None
    #: Shortcut: retarget a goto choice.
    target_node_id: str | None = None


class ChoiceOut(Out):
    id: str
    node_id: str
    position: int
    label: str
    kind: ChoiceKind
    condition: str | None
    unmet_display: UnmetDisplay
    print_text: str | None
    min_tier: str | None
    effects: list[Effect]
    dice: str | None
    test: str | None
    encounter_id: str | None
    flee_allowed: bool
    outcomes: list[OutcomeOut]


# ── encounters, items, shop ──────────────────────────────────────────────


class EncounterEnemyIn(In):
    enemy_id: str
    level: int = Field(default=1, ge=1)
    count: int = Field(default=1, ge=1)


class EncounterEnemyOut(Out):
    id: str
    enemy_id: str
    level: int
    count: int


class EncounterIn(In):
    label: str = ""
    mode: Literal["fixed", "table"] = "fixed"
    fight: Literal["sequential", "simultaneous"] = "sequential"
    table_id: str | None = None
    enemies: list[EncounterEnemyIn] = Field(default_factory=list)


class EncounterOut(Out):
    id: str
    position: int
    label: str
    mode: Literal["fixed", "table"]
    fight: Literal["sequential", "simultaneous"]
    table_id: str | None
    enemies: list[EncounterEnemyOut]


class PlacementIn(In):
    item_id: str
    qty: int = Field(default=1, ge=1)


class PlacementOut(Out):
    id: str
    item_id: str
    qty: int


class ShopItemIn(In):
    item_id: str
    price: int = Field(default=0, ge=0)
    stock: int | None = Field(default=None, ge=0)


class ShopItemOut(Out):
    id: str
    item_id: str
    price: int
    stock: int | None


class ShopIn(In):
    is_shop: bool = True
    sell_rate: int | None = Field(
        default=None, ge=0, le=100, description="% of value paid when selling"
    )
    items: list[ShopItemIn] = Field(default_factory=list)


# ── node ─────────────────────────────────────────────────────────────────


class NodeOut(Out):
    id: str
    book_id: str
    act_id: str
    key: str
    title: str
    beat_notes: str
    summary: str
    is_act_entry: bool
    is_act_exit: bool
    ending_kind: EndingKind | None
    ending_grade: EndingGrade | None
    ending_label: str
    location_id: str | None
    canonical_predecessor_id: str | None
    style_override: dict[str, object]
    section_pin: int | None
    on_enter: list[Effect]
    is_shop: bool
    shop_sell_rate: int | None
    x: float
    y: float
    collapsed: bool
    character_ids: list[str]
    variants: list[VariantOut]
    choices: list[ChoiceOut]
    encounters: list[EncounterOut]
    items: list[PlacementOut]
    shop_items: list[ShopItemOut]
    #: Thumbnail of the first illustration with an image (canvas card), if any.
    art_thumb: str | None = None
