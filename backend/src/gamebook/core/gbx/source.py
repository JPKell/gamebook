"""Canonical gbx source printer (minimal parentheses)."""

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

# Binding power; higher binds tighter. Mirrors the parser.
_PREC = {"?": 1, "or": 2, "and": 3, "not": 4, "cmp": 5, "+": 6, "-": 6, "*": 7, "/": 7, "%": 7}
_UNARY_MINUS = 8
_ATOM = 9


def _prec(e: Expr) -> int:
    match e:
        case Ternary():
            return _PREC["?"]
        case Binary(op=op):
            return _PREC[op]
        case Unary(op="not"):
            return _PREC["not"]
        case Unary():
            return _UNARY_MINUS
        case Compare():
            return _PREC["cmp"]
        case Num(value=v) if v < 0:
            return _UNARY_MINUS
        case _:
            return _ATOM


def _wrap(e: Expr, min_prec: int) -> str:
    s = to_source(e)
    return f"({s})" if _prec(e) < min_prec else s


def to_source(e: Expr) -> str:
    match e:
        case Num(value=v):
            return str(v)
        case Bool(value=v):
            return "true" if v else "false"
        case Dice(count=c, sides=s):
            return f"{c}d{s}"
        case Name(name=n):
            return n
        case Attr(obj=o, attr=a):
            return f"{o}.{a}"
        case Call(func=f, args=args):
            return f"{f}({', '.join(to_source(a) for a in args)})"
        case Unary(op="not", operand=x):
            return f"not {_wrap(x, _PREC['not'])}"
        case Unary(op=_, operand=x):
            return f"-{_wrap(x, _UNARY_MINUS)}"
        case Binary(op=op, left=lhs, right=rhs):
            p = _PREC[op]
            # Left-associative: right operand needs strictly higher precedence.
            return f"{_wrap(lhs, p)} {op} {_wrap(rhs, p + 1)}"
        case Compare(op=op, left=lhs, right=rhs):
            p = _PREC["cmp"]
            return f"{_wrap(lhs, p + 1)} {op} {_wrap(rhs, p + 1)}"
        case Ternary(cond=c, then=t, otherwise=o):
            p = _PREC["?"]
            return f"{_wrap(c, p + 1)} ? {_wrap(t, p)} : {_wrap(o, p)}"
    raise TypeError(f"not an expression: {e!r}")
