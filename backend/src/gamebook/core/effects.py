"""Effects: structured state changes on node entry, choices, tests, items."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from gamebook.core import gbx
from gamebook.core.gbx.english import Namer, default_namer
from gamebook.core.gbx.scope import RefKind, Scope


class _EffectBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Fire only on the first visit. None = default for the op (gains: once).
    once: bool | None = None
    #: Only applies at this tier or above.
    min_tier: str | None = None
    #: Author override for print/English rendering.
    print_text: str | None = None


class ModifyStat(_EffectBase):
    op: Literal["modify"] = "modify"
    stat: str
    amount: str = Field(description="gbx number, e.g. '-2' or '1d6'")


class SetStat(_EffectBase):
    op: Literal["set"] = "set"
    stat: str
    value: str = Field(description="gbx number")


class GiveItem(_EffectBase):
    op: Literal["give"] = "give"
    item: str
    qty: int = Field(default=1, ge=1)


class TakeItem(_EffectBase):
    op: Literal["take"] = "take"
    item: str
    qty: int = Field(default=1, ge=1)


class EquipItem(_EffectBase):
    op: Literal["equip"] = "equip"
    item: str


class SetFlag(_EffectBase):
    op: Literal["set_flag"] = "set_flag"
    flag: str


class ClearFlag(_EffectBase):
    op: Literal["clear_flag"] = "clear_flag"
    flag: str


class LearnSkill(_EffectBase):
    op: Literal["learn"] = "learn"
    skill: str


Effect = Annotated[
    ModifyStat | SetStat | GiveItem | TakeItem | EquipItem | SetFlag | ClearFlag | LearnSkill,
    Field(discriminator="op"),
]

GAIN_OPS = frozenset({"give", "equip", "set_flag", "learn"})


def fires_once(effect: Effect) -> bool:
    return effect.once if effect.once is not None else effect.op in GAIN_OPS


# ── references ───────────────────────────────────────────────────────────


def effect_refs(effect: Effect, amount_scope: Scope) -> list[tuple[RefKind, str, str]]:
    """``(kind, key, role)`` for everything an effect mentions."""
    role = f"effect.{effect.op}"
    out: list[tuple[RefKind, str, str]] = []
    match effect:
        case ModifyStat(stat=s, amount=src) | SetStat(stat=s, value=src):
            out.append((RefKind.STAT, s, role))
            out.extend((r.kind, r.key, role) for r in _expr_refs(src, amount_scope))
        case GiveItem(item=i) | TakeItem(item=i) | EquipItem(item=i):
            out.append((RefKind.ITEM, i, role))
        case SetFlag(flag=f):
            out.append((RefKind.FLAG, f, "effect.set_flag"))
        case ClearFlag(flag=f):
            out.append((RefKind.FLAG, f, "effect.clear_flag"))
        case LearnSkill(skill=s):
            out.append((RefKind.SKILL, s, role))
    if effect.min_tier:
        out.append((RefKind.TIER, effect.min_tier, role))
    return out


def _expr_refs(src: str, scope: Scope) -> list[gbx.Reference]:
    try:
        return gbx.references(gbx.parse(src), scope)
    except gbx.GbxSyntaxError:
        return []


def rename_in_effect(effect: Effect, scope: Scope, kind: RefKind, old: str, new: str) -> Effect:
    """Return the effect with every ``kind`` reference ``old`` renamed to ``new``."""
    data = effect.model_dump()
    field_for = {
        RefKind.ITEM: "item",
        RefKind.FLAG: "flag",
        RefKind.SKILL: "skill",
        RefKind.STAT: "stat",
    }
    f = field_for.get(kind)
    if f and data.get(f) == old:
        data[f] = new
    for expr_field in ("amount", "value"):
        if expr_field in data:
            data[expr_field] = gbx.rename_in_source(data[expr_field], scope, kind, old, new)
    if kind == RefKind.TIER and data.get("min_tier") == old:
        data["min_tier"] = new
    return type(effect).model_validate(data)


# ── English ──────────────────────────────────────────────────────────────


def effect_to_english(effect: Effect, namer: Namer = default_namer) -> str:
    """Imperative sentence, e.g. "Deduct 2 from your STAMINA."."""
    if effect.print_text:
        return effect.print_text
    match effect:
        case ModifyStat(stat=s, amount=src):
            label = namer(RefKind.STAT, s)
            try:
                e = gbx.parse(src)
            except gbx.GbxSyntaxError:
                return f"Adjust your {label} by {src}."
            if isinstance(e, gbx.ast.Num):
                return f"Add {e.value} to your {label}."
            if isinstance(e, gbx.ast.Unary) and e.op == "-" and isinstance(e.operand, gbx.ast.Num):
                return f"Deduct {e.operand.value} from your {label}."
            return f"Add {gbx.number_to_english(e, namer)} to your {label}."
        case SetStat(stat=s, value=src):
            try:
                value = gbx.number_to_english(gbx.parse(src), namer)
            except gbx.GbxSyntaxError:
                value = src
            return f"Set your {namer(RefKind.STAT, s)} to {value}."
        case GiveItem(item=i, qty=q):
            name = namer(RefKind.ITEM, i)
            return f"You gain the {name}." if q == 1 else f"You gain {q} {name}."
        case TakeItem(item=i, qty=q):
            name = namer(RefKind.ITEM, i)
            return f"You lose the {name}." if q == 1 else f"You lose {q} {name}."
        case EquipItem(item=i):
            return f"You equip the {namer(RefKind.ITEM, i)}."
        case SetFlag(flag=f):
            return f"Note the codeword {namer(RefKind.FLAG, f)}."
        case ClearFlag(flag=f):
            return f"Cross out the codeword {namer(RefKind.FLAG, f)}."
        case LearnSkill(skill=s):
            return f"You learn the skill of {namer(RefKind.SKILL, s)}."
    raise TypeError(effect)
