"""Compile gbx ASTs to Python closures for hot paths (simulation, combat lab).

Semantics are identical to ``evaluator`` (the reference implementation; a
property test checks equivalence) but avoid per-node dispatch and use plain
ints, switching to exact ``Fraction`` only when a division doesn't divide.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from fractions import Fraction

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
from gamebook.core.gbx.errors import GbxEvalError
from gamebook.core.gbx.evaluator import Env, Rng, TierValue
from gamebook.core.gbx.scope import MATH_FUNCTIONS, REF_FUNCTIONS

Number = int | Fraction
CValue = Number | bool | TierValue
Compiled = Callable[[Env, Rng | None], CValue]


def _norm(x: Number) -> Number:
    """Collapse integral Fractions back to int (keeps the fast path fast)."""
    if isinstance(x, Fraction) and x.denominator == 1:
        return int(x.numerator)
    return x


def _min(values: list[Number]) -> Number:
    best = values[0]
    for v in values[1:]:
        if v < best:
            best = v
    return best


def _max(values: list[Number]) -> Number:
    best = values[0]
    for v in values[1:]:
        if v > best:
            best = v
    return best


def _clamp(v: Number, lo: Number, hi: Number) -> Number:
    return _max([lo, _min([hi, v])])


def _abs(v: Number) -> Number:
    return -v if v < 0 else v


# Nodes whose compiled closure can only produce a number / a bool, so the
# runtime type check can be skipped (a big win in hot loops).
def _always_number(e: Expr) -> bool:
    match e:
        case Num() | Dice() | Attr():
            return True
        case Unary(op="-") | Binary(op="+" | "-" | "*" | "/" | "%"):
            return True
        case Call(func=f) if f not in REF_FUNCTIONS:
            return True
        case Call(func=f) if f in ("count", "visits"):
            return True
    return False


def _always_bool(e: Expr) -> bool:
    match e:
        case Bool() | Compare() | Unary(op="not") | Binary(op="and" | "or"):
            return True
        case Call(func=f) if f in REF_FUNCTIONS and f not in ("count", "visits"):
            return True
    return False


def _number_of(e: Expr, bare_object: str | None) -> Callable[[Env, Rng | None], Number]:
    f = compile_expr(e, bare_object)
    return f if _always_number(e) else _num(f)  # type: ignore[return-value]


def _bool_of(e: Expr, bare_object: str | None) -> Callable[[Env, Rng | None], bool]:
    f = compile_expr(e, bare_object)
    return f if _always_bool(e) else _bool(f)  # type: ignore[return-value]


def _num(f: Compiled) -> Callable[[Env, Rng | None], Number]:
    def g(env: Env, rng: Rng | None) -> Number:
        v = f(env, rng)
        if isinstance(v, bool) or not isinstance(v, int | Fraction):
            raise GbxEvalError(f"expected a number, got {v!r}")
        return v

    return g


def _bool(f: Compiled) -> Callable[[Env, Rng | None], bool]:
    def g(env: Env, rng: Rng | None) -> bool:
        v = f(env, rng)
        if not isinstance(v, bool):
            raise GbxEvalError(f"expected true/false, got {v!r}")
        return v

    return g


def compile_expr(e: Expr, bare_object: str | None = "player") -> Compiled:
    match e:
        case Num(value=v):
            return lambda env, rng: v
        case Bool(value=flag):
            return lambda env, rng: flag
        case Dice(count=dice_count, sides=dice_sides):

            def dice(env: Env, rng: Rng | None) -> CValue:
                if rng is None:
                    raise GbxEvalError("dice rolled without a random source")
                return sum(rng.roll(dice_count, dice_sides))

            return dice
        case Name(name=n):

            def name(env: Env, rng: Rng | None) -> CValue:
                var = env.variable(n)
                if var is not None:
                    return _norm(var) if isinstance(var, Fraction) else var
                if n == "tier":
                    if env.current_tier not in env.tiers:
                        raise GbxEvalError(f"current tier {env.current_tier!r} is unknown")
                    return TierValue(list(env.tiers).index(env.current_tier))
                if n in env.tiers:
                    return TierValue(list(env.tiers).index(n))
                if bare_object is not None:
                    return env.stat(bare_object, n)
                raise GbxEvalError(f"unknown name {n}")

            return name
        case Attr(obj=attr_obj, attr=attr_key):
            return lambda env, rng: env.stat(attr_obj, attr_key)
        case Call(func=f, args=args) if f in REF_FUNCTIONS:
            fn = REF_FUNCTIONS[f]
            arg = args[0] if len(args) == 1 else None
            if not isinstance(arg, Name):

                def bad(env: Env, rng: Rng | None) -> CValue:
                    raise GbxEvalError(f"{f}() needs a key")

                return bad
            key = arg.name
            kind = fn.kind

            def ref(env: Env, rng: Rng | None) -> CValue:
                r = env.ref(f, kind, key)
                return r if isinstance(r, bool) else int(r)

            return ref
        case Call(func=f, args=args):
            arity = MATH_FUNCTIONS.get(f)
            if arity is not None and (
                len(args) < arity[0] or (arity[1] is not None and len(args) > arity[1])
            ):
                count = len(args)

                def bad_arity(env: Env, rng: Rng | None) -> CValue:
                    raise GbxEvalError(f"{f}() got {count} argument(s)")

                return bad_arity
            parts = [_number_of(a, bare_object) for a in args]
            match f:
                case "min":
                    return lambda env, rng: _min([p(env, rng) for p in parts])
                case "max":
                    return lambda env, rng: _max([p(env, rng) for p in parts])
                case "floor":
                    return lambda env, rng: math.floor(parts[0](env, rng))
                case "ceil":
                    return lambda env, rng: math.ceil(parts[0](env, rng))
                case "round":
                    return lambda env, rng: math.floor(parts[0](env, rng) + Fraction(1, 2))
                case "abs":
                    return lambda env, rng: _abs(parts[0](env, rng))
                case "clamp":
                    # Evaluate in source order (value, lo, hi) so dice draws match the evaluator.
                    return lambda env, rng: _clamp(
                        parts[0](env, rng), parts[1](env, rng), parts[2](env, rng)
                    )

            def unknown(env: Env, rng: Rng | None) -> CValue:
                raise GbxEvalError(f"unknown function {f}")

            return unknown
        case Unary(op="not", operand=x):
            inner_b = _bool_of(x, bare_object)
            return lambda env, rng: not inner_b(env, rng)
        case Unary(operand=x):
            inner_n = _number_of(x, bare_object)
            return lambda env, rng: -inner_n(env, rng)
        case Binary(op="and", left=lhs, right=rhs):
            lb, rb = _bool_of(lhs, bare_object), _bool_of(rhs, bare_object)
            return lambda env, rng: lb(env, rng) and rb(env, rng)
        case Binary(op="or", left=lhs, right=rhs):
            lb, rb = _bool_of(lhs, bare_object), _bool_of(rhs, bare_object)
            return lambda env, rng: lb(env, rng) or rb(env, rng)
        case Binary(op=op, left=lhs, right=rhs):
            ln, rn = _number_of(lhs, bare_object), _number_of(rhs, bare_object)
            if op == "+":
                return lambda env, rng: ln(env, rng) + rn(env, rng)
            if op == "-":
                return lambda env, rng: ln(env, rng) - rn(env, rng)
            if op == "*":
                return lambda env, rng: ln(env, rng) * rn(env, rng)

            def div(env: Env, rng: Rng | None) -> CValue:
                a, b = ln(env, rng), rn(env, rng)
                if b == 0:
                    raise GbxEvalError("division by zero")
                if op == "%":
                    return (
                        _norm(a % b)
                        if isinstance(a, Fraction) or isinstance(b, Fraction)
                        else a % b
                    )
                if isinstance(a, int) and isinstance(b, int):
                    return a // b if a % b == 0 else Fraction(a, b)
                return _norm(Fraction(a) / Fraction(b))

            return div
        case Compare(op=op, left=lhs, right=rhs):
            lf, rf = compile_expr(lhs, bare_object), compile_expr(rhs, bare_object)

            def cmp(env: Env, rng: Rng | None) -> CValue:
                a, b = lf(env, rng), rf(env, rng)
                if op == "==":
                    return a == b
                if op == "!=":
                    return a != b
                ordered = (isinstance(a, TierValue) and isinstance(b, TierValue)) or (
                    isinstance(a, int | Fraction)
                    and isinstance(b, int | Fraction)
                    and not isinstance(a, bool)
                    and not isinstance(b, bool)
                )
                if not ordered:
                    raise GbxEvalError(f"can't order {a!r} and {b!r}")
                if op == "<":
                    return a < b  # type: ignore[operator]
                if op == "<=":
                    return a <= b  # type: ignore[operator]
                if op == ">":
                    return a > b  # type: ignore[operator]
                return a >= b  # type: ignore[operator]

            return cmp
        case Ternary(cond=c, then=t, otherwise=o):
            cb, tf, of = (
                _bool(compile_expr(c, bare_object)),
                compile_expr(t, bare_object),
                compile_expr(o, bare_object),
            )
            return lambda env, rng: tf(env, rng) if cb(env, rng) else of(env, rng)
    raise GbxEvalError(f"cannot compile {e!r}")


#: Integer results beyond this are errors in both engines (the TS player stores
#: numbers as doubles, which are exact only up to 2**53).
MAX_INT = 2**53


def compile_int(e: Expr, bare_object: str | None = "player") -> Callable[[Env, Rng | None], int]:
    """Compiled number, rounded down (like ``evaluate_int``)."""
    f = _number_of(e, bare_object)

    def run(env: Env, rng: Rng | None) -> int:
        value = math.floor(f(env, rng))
        if abs(value) > MAX_INT:
            raise GbxEvalError("number too large")
        return value

    return run


def compile_bool(e: Expr, bare_object: str | None = "player") -> Callable[[Env, Rng | None], bool]:
    return _bool_of(e, bare_object)
