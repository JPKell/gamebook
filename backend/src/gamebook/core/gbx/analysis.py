"""Static numeric analysis: value ranges and exact dice distributions."""

from __future__ import annotations

import math
from collections.abc import Mapping
from fractions import Fraction

from gamebook.core.gbx.ast import Binary, Call, Dice, Expr, Name, Num, Ternary, Unary

Interval = tuple[Fraction, Fraction]


def value_range(expr: Expr, known: Mapping[str, Interval] | None = None) -> Interval | None:
    """Inclusive (min, max) of a numeric expression, or None if it can't be bounded.

    ``known`` gives ranges for bare names (variables like ``level``). Ranges are
    sound but may be loose (e.g. ``1d6 - 1d6`` is reported as -5..5).
    """
    known = known or {}

    def go(e: Expr) -> Interval | None:
        match e:
            case Num(value=v):
                return (Fraction(v), Fraction(v))
            case Dice(count=c, sides=s):
                return (Fraction(c), Fraction(c * s))
            case Name(name=n) if n in known:
                return known[n]
            case Unary(op="-", operand=x):
                r = go(x)
                return None if r is None else (-r[1], -r[0])
            case Binary(op="+" | "-" | "*" | "/" as op, left=lhs, right=rhs):
                a, b = go(lhs), go(rhs)
                if a is None or b is None:
                    return None
                if op == "+":
                    return (a[0] + b[0], a[1] + b[1])
                if op == "-":
                    return (a[0] - b[1], a[1] - b[0])
                if op == "/":
                    if b[0] <= 0 <= b[1]:
                        return None
                    b = (1 / b[1], 1 / b[0])
                products = [x * y for x in a for y in b]
                return (min(products), max(products))
            case Call(func=f, args=args) if f in (
                "min",
                "max",
                "floor",
                "ceil",
                "round",
                "abs",
                "clamp",
            ):
                rs = [go(a) for a in args]
                if any(r is None for r in rs):
                    return None
                ivs: list[Interval] = [r for r in rs if r is not None]
                if f == "min":
                    return (min(r[0] for r in ivs), min(r[1] for r in ivs))
                if f == "max":
                    return (max(r[0] for r in ivs), max(r[1] for r in ivs))
                if f == "floor":
                    return (Fraction(math.floor(ivs[0][0])), Fraction(math.floor(ivs[0][1])))
                if f == "ceil":
                    return (Fraction(math.ceil(ivs[0][0])), Fraction(math.ceil(ivs[0][1])))
                if f == "round":
                    half = Fraction(1, 2)
                    return (
                        Fraction(math.floor(ivs[0][0] + half)),
                        Fraction(math.floor(ivs[0][1] + half)),
                    )
                if f == "abs":
                    lo, hi = ivs[0]
                    if lo >= 0:
                        return (lo, hi)
                    if hi <= 0:
                        return (-hi, -lo)
                    return (Fraction(0), max(-lo, hi))
                val, lo_r, hi_r = ivs
                return (
                    max(lo_r[0], min(hi_r[0], val[0])),
                    max(lo_r[1], min(hi_r[1], val[1])),
                )
            case Ternary(then=t, otherwise=o):
                a, b = go(t), go(o)
                if a is None or b is None:
                    return None
                return (min(a[0], b[0]), max(a[1], b[1]))
        return None

    return go(expr)


def integer_range(
    expr: Expr, known: Mapping[str, Interval] | None = None
) -> tuple[int, int] | None:
    """Range after rounding down, as stats/branches see it."""
    r = value_range(expr, known)
    return None if r is None else (math.floor(r[0]), math.floor(r[1]))


#: Upper bound on the number of distinct sums we'll enumerate.
MAX_DISTRIBUTION_SPAN = 2000


def distribution(expr: Expr) -> dict[int, Fraction] | None:
    """Exact probability of each outcome for sums of dice and constants.

    Supports ``+``, ``-``, unary minus and multiplication by a constant
    (e.g. ``2d6 + 3``, ``1d6 - 1d4``, ``2 * 1d6``). Returns None otherwise, or
    when the expression has too many possible sums to enumerate cheaply.
    """
    span = 0

    def go(e: Expr) -> tuple[dict[int, int], int] | None:
        """(ways to reach each value, total ways)."""
        nonlocal span
        match e:
            case Num(value=v):
                return {v: 1}, 1
            case Dice(count=c, sides=s):
                span += c * (s - 1) + 1
                if span > MAX_DISTRIBUTION_SPAN:
                    return None
                acc: dict[int, int] = {0: 1}
                die = dict.fromkeys(range(1, s + 1), 1)
                for _ in range(c):
                    acc = _convolve(acc, die)
                return acc, s**c
            case Unary(op="-", operand=x):
                r = go(x)
                return None if r is None else ({-k: w for k, w in r[0].items()}, r[1])
            case Binary(op="+" | "-" as op, left=lhs, right=rhs):
                a, b = go(lhs), go(rhs)
                if a is None or b is None:
                    return None
                b_ways = {-k: w for k, w in b[0].items()} if op == "-" else b[0]
                return _convolve(a[0], b_ways), a[1] * b[1]
            case (
                Binary(op="*", left=Num(value=k), right=x)
                | Binary(op="*", left=x, right=Num(value=k))
            ):
                r = go(x)
                return None if r is None else ({v * k: w for v, w in r[0].items()}, r[1])
        return None

    result = go(expr)
    if result is None:
        return None
    ways, total = result
    return {v: Fraction(w, total) for v, w in sorted(ways.items())}


def _convolve(a: dict[int, int], b: dict[int, int]) -> dict[int, int]:
    out: dict[int, int] = {}
    for x, p in a.items():
        for y, q in b.items():
            out[x + y] = out.get(x + y, 0) + p * q
    return out
