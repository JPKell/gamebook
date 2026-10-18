"""Static checking: names, types, determinism, printability, integrality."""

from __future__ import annotations

import difflib
from collections.abc import Iterable

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
    Span,
    Ternary,
    Unary,
    walk,
)
from gamebook.core.gbx.errors import Diagnostic, GbxSyntaxError
from gamebook.core.gbx.parser import parse
from gamebook.core.gbx.scope import (
    MATH_FUNCTIONS,
    REF_FUNCTIONS,
    ROUNDING_FUNCTIONS,
    GbxType,
    RefKind,
    Scope,
)


def _suggest(name: str, options: Iterable[str]) -> str:
    match = difflib.get_close_matches(name, list(options), n=1, cutoff=0.6)
    if not match:
        match = [o for o in options if o.lower() == name.lower()]
    return f" — did you mean {match[0]!r}?" if match else ""


class _Checker:
    def __init__(self, scope: Scope) -> None:
        self.scope = scope
        self.diags: list[Diagnostic] = []

    def error(self, code: str, msg: str, span: Span) -> None:
        self.diags.append(Diagnostic("error", code, msg, span))

    def warn(self, code: str, msg: str, span: Span) -> None:
        self.diags.append(Diagnostic("warning", code, msg, span))

    def expect(self, e: Expr, want: GbxType, what: str) -> None:
        got = self.infer(e)
        if got is not None and got != want:
            self.error("type", f"{what} must be a {want}, not a {got}", e.span)

    # Returns None when the type is unknown (an error was already reported).
    def infer(self, e: Expr) -> GbxType | None:
        sc = self.scope
        match e:
            case Num():
                return "number"
            case Bool():
                return "bool"
            case Dice():
                if not sc.allow_dice:
                    self.error("dice", "Dice can't be rolled here", e.span)
                return "number"
            case Name(name=n):
                if n in sc.variables:
                    return sc.variables[n]
                if n == "tier":
                    return "tier"
                if n in sc.tiers:
                    return "tier"
                if sc.bare_object and n in sc.objects.get(sc.bare_object, frozenset()):
                    return "number"
                options = [*sc.variables, *sc.tiers]
                if sc.bare_object:
                    options += sc.objects.get(sc.bare_object, frozenset())
                if n in REF_FUNCTIONS or n in MATH_FUNCTIONS:
                    self.error("name", f"{n!r} is a function; call it like {n}(...)", e.span)
                else:
                    self.error("name", f"Unknown name {n!r}{_suggest(n, options)}", e.span)
                return None
            case Attr(obj=o, attr=a):
                if o not in sc.objects:
                    self.error("name", f"Unknown object {o!r}{_suggest(o, sc.objects)}", e.span)
                    return None
                stats = sc.objects[o]
                if a not in stats:
                    self.error(
                        "stat",
                        f"{o} has no stat {a!r} in this tier{_suggest(a, stats)}",
                        e.attr_span,
                    )
                    return None
                return "number"
            case Call():
                return self.call(e)
            case Unary(op="not", operand=x):
                self.expect(x, "bool", "The operand of 'not'")
                return "bool"
            case Unary(operand=x):
                self.expect(x, "number", "The operand of '-'")
                return "number"
            case Binary(op="and" | "or" as op, left=lhs, right=rhs):
                self.expect(lhs, "bool", f"Both sides of '{op}'")
                self.expect(rhs, "bool", f"Both sides of '{op}'")
                return "bool"
            case Binary(op=op, left=lhs, right=rhs):
                self.expect(lhs, "number", f"Both sides of '{op}'")
                self.expect(rhs, "number", f"Both sides of '{op}'")
                if op in ("/", "%") and isinstance(rhs, Num) and rhs.value == 0:
                    self.error("div_zero", "Division by zero", rhs.span)
                return "number"
            case Compare(op=op, left=lhs, right=rhs):
                lt, rt = self.infer(lhs), self.infer(rhs)
                if lt is None or rt is None:
                    return "bool"
                if lt != rt:
                    self.error("type", f"Can't compare a {lt} with a {rt}", e.span)
                elif lt == "bool" and op not in ("==", "!="):
                    self.error("type", f"'{op}' needs numbers, not true/false values", e.span)
                return "bool"
            case Ternary(cond=c, then=t, otherwise=o):
                self.expect(c, "bool", "The condition before '?'")
                tt, ot = self.infer(t), self.infer(o)
                if tt is not None and ot is not None and tt != ot:
                    self.error("type", f"Both branches must have the same type ({tt}/{ot})", e.span)
                return tt or ot
        raise TypeError(e)

    def call(self, e: Call) -> GbxType | None:
        sc = self.scope
        if e.func in REF_FUNCTIONS:
            fn = REF_FUNCTIONS[e.func]
            if len(e.args) != 1 or not isinstance(e.args[0], Name):
                self.error("args", f"{fn.name}() takes one {fn.kind.value} key", e.span)
                return fn.returns
            arg = e.args[0]
            if fn.kind not in sc.refs:
                self.error("context", f"{fn.name}() can't be used here", e.span)
                return fn.returns
            known = sc.refs[fn.kind]
            if known is not None and arg.name not in known:
                self.error(
                    "ref",
                    f"Unknown {fn.kind.value} {arg.name!r}{_suggest(arg.name, known)}",
                    arg.span,
                )
            if not fn.printable:
                self.diags.append(
                    Diagnostic(
                        "info",
                        "unprintable",
                        f"{fn.name}() is tracked by hand in print editions "
                        "(tick boxes or split sections)",
                        e.span,
                    )
                )
            return fn.returns
        if e.func in MATH_FUNCTIONS:
            lo, hi = MATH_FUNCTIONS[e.func]
            n = len(e.args)
            if n < lo or (hi is not None and n > hi):
                want = str(lo) if lo == hi else f"at least {lo}"
                self.error("args", f"{e.func}() takes {want} argument(s), got {n}", e.span)
            for a in e.args:
                self.expect(a, "number", f"Arguments of {e.func}()")
            return "number"
        known_fns = [*REF_FUNCTIONS, *MATH_FUNCTIONS]
        self.error("name", f"Unknown function {e.func!r}{_suggest(e.func, known_fns)}", e.span)
        for a in e.args:
            self.infer(a)
        return None

    def check_integrality(self, e: Expr) -> None:
        """Warn when '/' may leave a fraction outside floor()/ceil()/round()."""

        def visit(node: Expr, rounded: bool) -> None:
            if isinstance(node, Call) and node.func in ROUNDING_FUNCTIONS:
                rounded = True
            if isinstance(node, Binary) and node.op == "/" and not rounded:
                self.warn(
                    "fraction",
                    "Division can leave a fraction; it will be rounded down. "
                    "Wrap it in floor(), ceil() or round() to make that explicit",
                    node.span,
                )
            match node:
                case Call(args=args):
                    for a in args:
                        visit(a, rounded)
                case Unary(operand=x):
                    visit(x, rounded)
                case Binary(left=lhs, right=rhs) | Compare(left=lhs, right=rhs):
                    visit(lhs, rounded)
                    visit(rhs, rounded)
                case Ternary(cond=c, then=t, otherwise=o):
                    visit(c, rounded)
                    visit(t, rounded)
                    visit(o, rounded)
                case _:
                    pass

        visit(e, False)


def check(expr: Expr, scope: Scope) -> list[Diagnostic]:
    """Type- and name-check an expression against a scope."""
    c = _Checker(scope)
    got = c.infer(expr)
    if got is not None and got != scope.expected:
        c.error("type", f"Expected a {scope.expected} expression, got a {got}", expr.span)
    if scope.require_integer:
        c.check_integrality(expr)
    return c.diags


def check_source(src: str, scope: Scope) -> tuple[Expr | None, list[Diagnostic]]:
    """Parse and check. Returns ``(None, [syntax error])`` on syntax errors."""
    try:
        expr = parse(src)
    except GbxSyntaxError as exc:
        return None, [exc.diagnostic()]
    return expr, check(expr, scope)


def is_random(expr: Expr) -> bool:
    return any(isinstance(n, Dice) for n in walk(expr))


def ref_kind_of_function(name: str) -> RefKind | None:
    fn = REF_FUNCTIONS.get(name)
    return fn.kind if fn else None
