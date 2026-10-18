"""gbx evaluation.

Numbers are exact fractions so ``level / 3`` behaves predictably; contexts that
need an integer floor the result (``evaluate_int``). Rounding helpers round half
up, which matches how gamebooks phrase it ("rounding fractions up").
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Protocol

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
from gamebook.core.gbx.scope import MATH_FUNCTIONS, REF_FUNCTIONS, RefKind


@dataclass(frozen=True, slots=True, order=True)
class TierValue:
    index: int


Value = Fraction | bool | TierValue


class Env(Protocol):
    """Runtime state an expression reads. Implemented by the engine."""

    tiers: Sequence[str]
    current_tier: str

    def variable(self, name: str) -> Value | None: ...
    def stat(self, obj: str, key: str) -> int: ...
    def ref(self, func: str, kind: RefKind, key: str) -> int | bool: ...


class Rng(Protocol):
    def roll(self, count: int, sides: int) -> list[int]: ...


_MASK64 = (1 << 64) - 1
_PCG_MULT = 6364136223846793005
_PCG_INC = 1442695040888963407  # any odd constant; fixed so streams are reproducible


@dataclass
class SeededRng:
    """Deterministic, portable dice (PCG32, XSH-RR) — every roll is recorded.

    The algorithm is fully specified so other runtimes (the TypeScript player)
    reproduce identical rolls from the same seed; Python's ``random`` would not
    be practical to port. Bounded rolls use rejection sampling (no modulo bias).
    """

    seed: int
    history: list[tuple[int, int, list[int]]] = field(default_factory=list)
    _state: int = field(init=False, repr=False, default=0)

    def __post_init__(self) -> None:
        self._state = 0
        self._next32()
        self._state = (self._state + (self.seed & _MASK64)) & _MASK64
        self._next32()

    def _next32(self) -> int:
        old = self._state
        self._state = (old * _PCG_MULT + _PCG_INC) & _MASK64
        xorshifted = (((old >> 18) ^ old) >> 27) & 0xFFFFFFFF
        rot = old >> 59
        return ((xorshifted >> rot) | (xorshifted << ((-rot) & 31))) & 0xFFFFFFFF

    def below(self, bound: int) -> int:
        """Uniform integer in [0, bound)."""
        threshold = (0x100000000 - bound) % bound
        while True:
            r = self._next32()
            if r >= threshold:
                return r % bound

    def roll(self, count: int, sides: int) -> list[int]:
        faces = [self.below(sides) + 1 for _ in range(count)]
        self.history.append((count, sides, faces))
        return faces


@dataclass
class SimpleEnv:
    """Dictionary-backed Env for tests, tools and previews."""

    tiers: Sequence[str] = ()
    current_tier: str = ""
    variables: dict[str, Value] = field(default_factory=dict)
    stats: dict[str, dict[str, int]] = field(default_factory=dict)
    items: dict[str, int] = field(default_factory=dict)
    equipped_items: set[str] = field(default_factory=set)
    flags: set[str] = field(default_factory=set)
    skills: set[str] = field(default_factory=set)
    classes: set[str] = field(default_factory=set)
    visit_counts: dict[str, int] = field(default_factory=dict)

    def variable(self, name: str) -> Value | None:
        return self.variables.get(name)

    def stat(self, obj: str, key: str) -> int:
        try:
            return self.stats[obj][key]
        except KeyError:
            raise GbxEvalError(f"{obj} has no stat {key}") from None

    def ref(self, func: str, kind: RefKind, key: str) -> int | bool:
        match func:
            case "has":
                return self.items.get(key, 0) > 0
            case "count":
                return self.items.get(key, 0)
            case "equipped":
                return key in self.equipped_items
            case "flag":
                return key in self.flags
            case "skill":
                return key in self.skills
            case "class":
                return key in self.classes
            case "visits":
                return self.visit_counts.get(key, 0)
        raise GbxEvalError(f"unknown function {func}")


def _round_half_up(x: Fraction) -> int:
    return math.floor(x + Fraction(1, 2))


class _Evaluator:
    def __init__(self, env: Env, rng: Rng | None, bare_object: str | None) -> None:
        self.env = env
        self.rng = rng
        self.bare_object = bare_object

    def num(self, e: Expr) -> Fraction:
        v = self.eval(e)
        if isinstance(v, bool) or not isinstance(v, Fraction):
            raise GbxEvalError(f"expected a number, got {v!r}")
        return v

    def bool_(self, e: Expr) -> bool:
        v = self.eval(e)
        if not isinstance(v, bool):
            raise GbxEvalError(f"expected true/false, got {v!r}")
        return v

    def eval(self, e: Expr) -> Value:
        match e:
            case Num(value=v):
                return Fraction(v)
            case Bool(value=v):
                return v
            case Dice(count=c, sides=s):
                if self.rng is None:
                    raise GbxEvalError("dice rolled without a random source")
                return Fraction(sum(self.rng.roll(c, s)))
            case Name(name=n):
                var_value = self.env.variable(n)
                if var_value is not None:
                    return var_value
                if n == "tier":
                    if self.env.current_tier not in self.env.tiers:
                        raise GbxEvalError(f"current tier {self.env.current_tier!r} is unknown")
                    return TierValue(list(self.env.tiers).index(self.env.current_tier))
                if n in self.env.tiers:
                    return TierValue(list(self.env.tiers).index(n))
                if self.bare_object is not None:
                    return Fraction(self.env.stat(self.bare_object, n))
                raise GbxEvalError(f"unknown name {n}")
            case Attr(obj=o, attr=a):
                return Fraction(self.env.stat(o, a))
            case Call(func=f, args=args):
                return self.call(f, args)
            case Unary(op="not", operand=x):
                return not self.bool_(x)
            case Unary(operand=x):
                return -self.num(x)
            case Binary(op="and", left=lhs, right=rhs):
                return self.bool_(lhs) and self.bool_(rhs)
            case Binary(op="or", left=lhs, right=rhs):
                return self.bool_(lhs) or self.bool_(rhs)
            case Binary(op=arith_op, left=lhs, right=rhs):
                return self.arith(arith_op, self.num(lhs), self.num(rhs))
            case Compare(op=cmp_op, left=lhs, right=rhs):
                return self.compare(cmp_op, self.eval(lhs), self.eval(rhs))
            case Ternary(cond=c, then=t, otherwise=o):
                return self.eval(t) if self.bool_(c) else self.eval(o)
        raise GbxEvalError(f"cannot evaluate {e!r}")

    @staticmethod
    def arith(op: str, a: Fraction, b: Fraction) -> Fraction:
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if b == 0:
            raise GbxEvalError("division by zero")
        return a / b if op == "/" else a % b

    @staticmethod
    def compare(op: str, a: Value, b: Value) -> bool:
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if isinstance(a, Fraction) and isinstance(b, Fraction):
            pair: tuple[Fraction | TierValue, Fraction | TierValue] = (a, b)
        elif isinstance(a, TierValue) and isinstance(b, TierValue):
            pair = (a, b)
        else:
            raise GbxEvalError(f"can't order {a!r} and {b!r}")
        x, y = pair
        if op == "<":
            return x < y  # type: ignore[operator]
        if op == "<=":
            return x <= y  # type: ignore[operator]
        if op == ">":
            return x > y  # type: ignore[operator]
        return x >= y  # type: ignore[operator]

    def call(self, f: str, args: tuple[Expr, ...]) -> Value:
        if f in REF_FUNCTIONS:
            fn = REF_FUNCTIONS[f]
            arg = args[0] if len(args) == 1 else None
            if not isinstance(arg, Name):
                raise GbxEvalError(f"{f}() needs a key")
            result = self.env.ref(f, fn.kind, arg.name)
            return result if isinstance(result, bool) else Fraction(result)
        arity = MATH_FUNCTIONS.get(f)
        if arity is not None and (
            len(args) < arity[0] or (arity[1] is not None and len(args) > arity[1])
        ):
            raise GbxEvalError(f"{f}() got {len(args)} argument(s)")
        vals = [self.num(a) for a in args]
        match f:
            case "min":
                return min(vals)
            case "max":
                return max(vals)
            case "floor":
                return Fraction(math.floor(vals[0]))
            case "ceil":
                return Fraction(math.ceil(vals[0]))
            case "round":
                return Fraction(_round_half_up(vals[0]))
            case "abs":
                return abs(vals[0])
            case "clamp":
                return max(vals[1], min(vals[2], vals[0]))
        raise GbxEvalError(f"unknown function {f}")


def evaluate(
    expr: Expr, env: Env, rng: Rng | None = None, *, bare_object: str | None = "player"
) -> Value:
    return _Evaluator(env, rng, bare_object).eval(expr)


def evaluate_number(
    expr: Expr, env: Env, rng: Rng | None = None, *, bare_object: str | None = "player"
) -> Fraction:
    return _Evaluator(env, rng, bare_object).num(expr)


def evaluate_int(
    expr: Expr, env: Env, rng: Rng | None = None, *, bare_object: str | None = "player"
) -> int:
    """Evaluate a number and round down (fractions round down, as in most gamebooks)."""
    return math.floor(evaluate_number(expr, env, rng, bare_object=bare_object))


def evaluate_bool(
    expr: Expr, env: Env, rng: Rng | None = None, *, bare_object: str | None = "player"
) -> bool:
    return _Evaluator(env, rng, bare_object).bool_(expr)
