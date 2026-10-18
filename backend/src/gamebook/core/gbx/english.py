"""Render gbx as plain English for print editions and editor previews.

Conditions render as a clause that fits "If ___, turn to 123." Numbers render
as phrases ("two dice plus your SKILL"). Labels for keys come from a ``Namer``.
Authors can always override the rendering per choice/effect.
"""

from __future__ import annotations

from collections.abc import Callable

from gamebook.core.gbx.ast import (
    Attr,
    Binary,
    Bool,
    Call,
    Compare,
    Dice,
    Expr,
    Name,
    Num,
    Ternary,
    Unary,
)
from gamebook.core.gbx.scope import RefKind

Namer = Callable[[RefKind, str], str]

_NUMBER_WORDS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
]

_COMPARE_PHRASE = {
    ">=": "at least",
    ">": "more than",
    "<=": "at most",
    "<": "less than",
    "==": "exactly",
    "!=": "anything but",
}
_FLIP = {">=": "<=", ">": "<", "<=": ">=", "<": ">", "==": "==", "!=": "!="}
_NEGATE = {">=": "<", ">": "<=", "<=": ">", "<": ">=", "==": "!=", "!=": "=="}

_VARIABLE_PHRASE = {
    "roll": "the total rolled",
    "natural": "the dice rolled",
    "damage": "the damage",
    "level": "the level",
}

_OBJECT_POSSESSIVE = {
    "player": "your",
    "enemy": "your opponent's",
    "attacker": "the attacker's",
    "target": "the target's",
}


def default_namer(kind: RefKind, key: str) -> str:
    return key


def _is_ref_count(e: Expr) -> bool:
    return isinstance(e, Call) and e.func in ("count", "visits")


def _is_stat(e: Expr, bare: str | None) -> bool:
    return isinstance(e, Attr) or (
        isinstance(e, Name)
        and bare is not None
        and e.name not in _VARIABLE_PHRASE
        and e.name != "tier"
    )


class _English:
    def __init__(self, namer: Namer, tiers: tuple[str, ...], bare_object: str | None) -> None:
        self.namer = namer
        self.tiers = tiers
        self.bare = bare_object

    def label(self, kind: RefKind, key: str) -> str:
        return self.namer(kind, key)

    # ── conditions ──
    def cond(self, e: Expr, negate: bool = False) -> str:
        match e:
            case Bool(value=v):
                return "always" if v != negate else "never"
            case Unary(op="not", operand=x):
                return self.cond(x, not negate)
            case Binary(op="and" | "or" as op, left=lhs, right=rhs):
                # De Morgan keeps negations local and readable.
                joined = ("or" if op == "and" else "and") if negate else op
                parts = [self.cond_part(x, joined, negate) for x in (lhs, rhs)]
                return f" {joined} ".join(parts)
            case Call(func=f, args=(Name(name=key),)):
                not_ = " not" if negate else ""
                do_not = "do not " if negate else ""
                if f == "has":
                    return f"you {do_not}have the {self.label(RefKind.ITEM, key)}"
                if f == "equipped":
                    return f"you {do_not}have the {self.label(RefKind.ITEM, key)} equipped"
                if f == "flag":
                    return f"you {do_not}have the codeword {self.label(RefKind.FLAG, key)}"
                if f == "skill":
                    return f"you {do_not}have the skill of {self.label(RefKind.SKILL, key)}"
                if f == "class":
                    return f"you are{not_} a {self.label(RefKind.CLASS, key)}"
            case Compare(op=cmp_op, left=lhs, right=rhs):
                return self.compare(_NEGATE[cmp_op] if negate else cmp_op, lhs, rhs)
            case Ternary(cond=c, then=t, otherwise=o):
                return (
                    f"({self.cond(t, negate)} if {self.cond(c)}, otherwise {self.cond(o, negate)})"
                )
        inner = self.num(e)
        return f"it is not the case that {inner}" if negate else inner

    def cond_part(self, e: Expr, joined: str, negate: bool) -> str:
        text = self.cond(e, negate)
        is_other_bool_op = isinstance(e, Binary) and e.op in ("and", "or")
        if is_other_bool_op:
            inner_op = e.op if not negate else ("or" if e.op == "and" else "and")  # type: ignore[union-attr]
            if inner_op != joined:
                return f"({text})"
        return text

    def compare(self, op: str, lhs: Expr, rhs: Expr) -> str:
        # Put the "subject" (stat, count, tier) on the left.
        if isinstance(lhs, Num) and not isinstance(rhs, Num):
            lhs, rhs, op = rhs, lhs, _FLIP[op]
        phrase = _COMPARE_PHRASE[op]
        if isinstance(lhs, Name) and lhs.name == "tier" and isinstance(rhs, Name):
            tier = self.label(RefKind.TIER, rhs.name)
            return {
                ">=": f"you are playing at the {tier} tier or higher",
                ">": f"you are playing above the {tier} tier",
                "<=": f"you are playing at the {tier} tier or lower",
                "<": f"you are playing below the {tier} tier",
                "==": f"you are playing at the {tier} tier",
                "!=": f"you are not playing at the {tier} tier",
            }[op]
        if isinstance(lhs, Call) and lhs.func == "visits" and isinstance(rhs, Num):
            place = self.label(RefKind.NODE, _key(lhs))
            if (
                (op == ">=" and rhs.value == 1)
                or (op == ">" and rhs.value == 0)
                or (op == "!=" and rhs.value == 0)
            ):
                return f"you have been to {place} before"
            if (op == "==" and rhs.value == 0) or (op == "<" and rhs.value == 1):
                return f"you have not been to {place} before"
            return f"you have been to {place} {phrase} {self.times(rhs.value)}"
        if isinstance(lhs, Call) and lhs.func == "count" and isinstance(rhs, Num):
            return f"you have {phrase} {rhs.value} {self.label(RefKind.ITEM, _key(lhs))}"
        if _is_stat(lhs, self.bare):
            return f"{self.num(lhs)} is {phrase} {self.num(rhs)}"
        if op == "==":
            return f"{self.num(lhs)} equals {self.num(rhs)}"
        if op == "!=":
            return f"{self.num(lhs)} does not equal {self.num(rhs)}"
        return f"{self.num(lhs)} is {phrase} {self.num(rhs)}"

    @staticmethod
    def times(n: int) -> str:
        return "once" if n == 1 else "twice" if n == 2 else f"{n} times"

    # ── numbers ──
    def num(self, e: Expr, parent_prec: int = 0) -> str:
        match e:
            case Num(value=v):
                return str(v)
            case Bool(value=v):
                return "true" if v else "false"
            case Dice(count=c, sides=6):
                word = _NUMBER_WORDS[c] if c < len(_NUMBER_WORDS) else str(c)
                return f"{word} {'die' if c == 1 else 'dice'}"
            case Dice(count=c, sides=s):
                return f"{c}d{s}"
            case Name(name="tier"):
                return "your tier"
            case Name(name=n) if n in _VARIABLE_PHRASE:
                return _VARIABLE_PHRASE[n]
            case Name(name=n) if n in self.tiers:
                return f"the {self.label(RefKind.TIER, n)} tier"
            case Name(name=n):
                return f"{_OBJECT_POSSESSIVE.get(self.bare or '', 'your')} {self.label(RefKind.STAT, n)}"
            case Attr(obj=o, attr=a):
                return (
                    f"{_OBJECT_POSSESSIVE.get(o, o + chr(39) + 's')} {self.label(RefKind.STAT, a)}"
                )
            case Call(func="count", args=(Name(name=k),)):
                return f"the number of {self.label(RefKind.ITEM, k)} you have"
            case Call(func="visits", args=(Name(name=k),)):
                return f"the number of times you have been to {self.label(RefKind.NODE, k)}"
            case Call(func="floor", args=(x,)):
                return f"{self.num(x)}, rounded down"
            case Call(func="ceil", args=(x,)):
                return f"{self.num(x)}, rounded up"
            case Call(func="round", args=(x,)):
                return f"{self.num(x)}, rounded to the nearest whole number"
            case Call(func="abs", args=(x,)):
                return f"the size of {self.num(x)} (ignoring any minus sign)"
            case Call(func="min", args=args):
                return f"the lowest of {_list([self.num(a) for a in args])}"
            case Call(func="max", args=args):
                return f"the highest of {_list([self.num(a) for a in args])}"
            case Call(func="clamp", args=(x, lo, hi)):
                return f"{self.num(x)}, but no less than {self.num(lo)} and no more than {self.num(hi)}"
            case Unary(op="-", operand=x):
                return f"minus {self.num(x, 3)}"
            case Binary(op="+" | "-" | "*" | "/" | "%" as op, left=lhs, right=rhs):
                prec = 1 if op in "+-" else 2
                words = {"+": "plus", "-": "minus", "*": "times", "/": "divided by", "%": "modulo"}[
                    op
                ]
                text = f"{self.num(lhs, prec)} {words} {self.num(rhs, prec + 1)}"
                return f"({text})" if prec < parent_prec else text
            case Ternary(cond=c, then=t, otherwise=o):
                return f"({self.num(t)} if {self.cond(c)}, otherwise {self.num(o)})"
        return self.cond(e)


def _key(call: Call) -> str:
    arg = call.args[0] if call.args else None
    return arg.name if isinstance(arg, Name) else "?"


def _list(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def condition_to_english(
    expr: Expr,
    namer: Namer = default_namer,
    *,
    tiers: tuple[str, ...] = (),
    bare_object: str | None = "player",
) -> str:
    """A clause for "If ___, …" — e.g. "you have the Rope and your GOLD is at least 5"."""
    return _English(namer, tiers, bare_object).cond(expr)


def number_to_english(
    expr: Expr,
    namer: Namer = default_namer,
    *,
    tiers: tuple[str, ...] = (),
    bare_object: str | None = "player",
) -> str:
    """A noun phrase — e.g. "two dice plus your SKILL"."""
    return _English(namer, tiers, bare_object).num(expr)
