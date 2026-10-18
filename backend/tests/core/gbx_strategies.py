"""Hypothesis strategies producing well-typed gbx ASTs."""

from hypothesis import strategies as st

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

STATS = ("SKILL", "STAMINA", "LUCK", "GOLD")
ITEMS = ("rope", "potion", "silver_key")
FLAGS = ("RAVEN", "FIRE")
TIERS = ("basic", "medium", "advanced")

num_leaf: st.SearchStrategy[Expr] = st.one_of(
    st.integers(0, 50).map(Num),
    st.builds(Dice, st.integers(1, 4), st.sampled_from([4, 6, 10])),
    st.sampled_from(STATS).map(lambda s: Attr("player", s)),
    st.sampled_from(STATS).map(Name),
    st.sampled_from(ITEMS).map(lambda k: Call("count", (Name(k),))),
)

bool_leaf: st.SearchStrategy[Expr] = st.one_of(
    st.booleans().map(Bool),
    st.sampled_from(ITEMS).map(lambda k: Call("has", (Name(k),))),
    st.sampled_from(FLAGS).map(lambda k: Call("flag", (Name(k),))),
    st.sampled_from(TIERS).map(lambda t: Compare(">=", Name("tier"), Name(t))),
)


def _num_ext(children: st.SearchStrategy[Expr]) -> st.SearchStrategy[Expr]:
    return st.one_of(
        st.builds(Binary, st.sampled_from(["+", "-", "*"]), children, children),
        st.builds(lambda a: Binary("/", a, Num(2)), children),
        st.builds(lambda a: Unary("-", a), children),
        st.builds(lambda a, b: Call("max", (a, b)), children, children),
        st.builds(lambda a: Call("floor", (a,)), children),
        st.builds(lambda c, a, b: Ternary(c, a, b), bool_leaf, children, children),
    )


numbers: st.SearchStrategy[Expr] = st.recursive(num_leaf, _num_ext, max_leaves=12)


def _bool_ext(children: st.SearchStrategy[Expr]) -> st.SearchStrategy[Expr]:
    return st.one_of(
        st.builds(Binary, st.sampled_from(["and", "or"]), children, children),
        st.builds(lambda a: Unary("not", a), children),
        st.builds(Compare, st.sampled_from(["==", "!=", "<", "<=", ">", ">="]), numbers, numbers),
    )


booleans: st.SearchStrategy[Expr] = st.recursive(bool_leaf, _bool_ext, max_leaves=8)
