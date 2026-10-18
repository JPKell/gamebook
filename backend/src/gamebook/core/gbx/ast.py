"""gbx abstract syntax tree.

Nodes are immutable and compare structurally; spans are excluded from equality
so ``parse(to_source(e)) == e`` holds. Every node serialises to plain JSON via
``to_json`` / ``from_json`` (used by the game bundle and the TS runtime).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ArithOp = Literal["+", "-", "*", "/", "%"]
BoolOp = Literal["and", "or"]
CompareOp = Literal["==", "!=", "<", "<=", ">", ">="]
UnaryOp = Literal["-", "not"]


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int


_NO_SPAN = Span(0, 0)


def _span() -> Any:
    return field(default=_NO_SPAN, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Num:
    value: int
    span: Span = _span()


@dataclass(frozen=True, slots=True)
class Bool:
    value: bool
    span: Span = _span()


@dataclass(frozen=True, slots=True)
class Dice:
    count: int
    sides: int
    span: Span = _span()


@dataclass(frozen=True, slots=True)
class Name:
    """A bare identifier: variable, constant, bare stat, or a reference key."""

    name: str
    span: Span = _span()


@dataclass(frozen=True, slots=True)
class Attr:
    """``obj.attr`` — e.g. ``player.SKILL``. ``attr_span`` locates the attribute."""

    obj: str
    attr: str
    span: Span = _span()
    attr_span: Span = _span()


@dataclass(frozen=True, slots=True)
class Call:
    func: str
    args: tuple[Expr, ...]
    span: Span = _span()


@dataclass(frozen=True, slots=True)
class Unary:
    op: UnaryOp
    operand: Expr
    span: Span = _span()


@dataclass(frozen=True, slots=True)
class Binary:
    op: ArithOp | BoolOp
    left: Expr
    right: Expr
    span: Span = _span()


@dataclass(frozen=True, slots=True)
class Compare:
    op: CompareOp
    left: Expr
    right: Expr
    span: Span = _span()


@dataclass(frozen=True, slots=True)
class Ternary:
    cond: Expr
    then: Expr
    otherwise: Expr
    span: Span = _span()


Expr = Num | Bool | Dice | Name | Attr | Call | Unary | Binary | Compare | Ternary


def children(e: Expr) -> tuple[Expr, ...]:
    match e:
        case Call(args=args):
            return args
        case Unary(operand=o):
            return (o,)
        case Binary(left=lhs, right=rhs) | Compare(left=lhs, right=rhs):
            return (lhs, rhs)
        case Ternary(cond=c, then=t, otherwise=o):
            return (c, t, o)
        case _:
            return ()


def walk(e: Expr) -> list[Expr]:
    """All nodes, pre-order."""
    out: list[Expr] = []
    stack = [e]
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend(reversed(children(node)))
    return out


# ── JSON ────────────────────────────────────────────────────────────────


def to_json(e: Expr) -> dict[str, Any]:
    match e:
        case Num(value=v):
            return {"t": "num", "v": v}
        case Bool(value=v):
            return {"t": "bool", "v": v}
        case Dice(count=c, sides=s):
            return {"t": "dice", "n": c, "s": s}
        case Name(name=n):
            return {"t": "name", "n": n}
        case Attr(obj=o, attr=a):
            return {"t": "attr", "o": o, "a": a}
        case Call(func=f, args=args):
            return {"t": "call", "f": f, "a": [to_json(x) for x in args]}
        case Unary(op=op, operand=x):
            return {"t": "unary", "op": op, "x": to_json(x)}
        case Binary(op=op, left=lhs, right=rhs):
            return {"t": "bin", "op": op, "l": to_json(lhs), "r": to_json(rhs)}
        case Compare(op=op, left=lhs, right=rhs):
            return {"t": "cmp", "op": op, "l": to_json(lhs), "r": to_json(rhs)}
        case Ternary(cond=c, then=t, otherwise=o):
            return {"t": "if", "c": to_json(c), "y": to_json(t), "n": to_json(o)}
    raise TypeError(f"not an expression: {e!r}")


def from_json(d: dict[str, Any]) -> Expr:
    t = d["t"]
    if t == "num":
        return Num(int(d["v"]))
    if t == "bool":
        return Bool(bool(d["v"]))
    if t == "dice":
        return Dice(int(d["n"]), int(d["s"]))
    if t == "name":
        return Name(str(d["n"]))
    if t == "attr":
        return Attr(str(d["o"]), str(d["a"]))
    if t == "call":
        return Call(str(d["f"]), tuple(from_json(x) for x in d["a"]))
    if t == "unary":
        return Unary(d["op"], from_json(d["x"]))
    if t == "bin":
        return Binary(d["op"], from_json(d["l"]), from_json(d["r"]))
    if t == "cmp":
        return Compare(d["op"], from_json(d["l"]), from_json(d["r"]))
    if t == "if":
        return Ternary(from_json(d["c"]), from_json(d["y"]), from_json(d["n"]))
    raise ValueError(f"unknown gbx node type {t!r}")
