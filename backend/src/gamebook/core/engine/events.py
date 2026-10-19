"""Engine events and actions (plain, JSON-friendly)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ActionType = Literal[
    "choose", "take", "buy", "sell", "use", "equip", "unequip", "attack", "flee", "choose_class"
]


@dataclass(frozen=True)
class Action:
    """Something the reader can do. ``target`` is a choice/item id, slot, or index key."""

    type: ActionType
    target: str | None = None
    label: str = ""
    enabled: bool = True
    #: Why a listed action is disabled (e.g. "Not enough Gold").
    reason: str | None = None

    def key(self) -> tuple[str, str | None]:
        return (self.type, self.target)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type}
        if self.target is not None:
            out["target"] = self.target
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Action:
        return cls(type=d["type"], target=d.get("target"))


@dataclass(frozen=True)
class Event:
    """One thing that happened. Serialises as ``{"type": ..., **data}``."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **self.data}
