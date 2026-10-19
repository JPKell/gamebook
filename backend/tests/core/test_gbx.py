import contextlib
import re
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gamebook.core import gbx
from gamebook.core.gbx.ast import Attr, Binary, Call, Dice, Name, Num, walk
from gamebook.core.gbx.scope import Context, RefKind, ScopeInputs

from .gbx_strategies import ITEMS, STATS, TIERS, booleans, numbers

INPUTS = ScopeInputs(
    player_stats=frozenset(STATS),
    enemy_stats=frozenset({"SKILL", "STAMINA", "ARMOR"}),
    tiers=TIERS,
    items=frozenset(ITEMS),
    skills=frozenset({"TRACKING"}),
    classes=frozenset({"ranger"}),
    nodes=frozenset({"a1_bridge"}),
)
COND = gbx.scope_for(Context.CONDITION, INPUTS)
AMOUNT = gbx.scope_for(Context.AMOUNT, INPUTS)


def env(**kw: object) -> gbx.SimpleEnv:
    base: dict[str, object] = {
        "tiers": TIERS,
        "current_tier": "medium",
        "stats": {"player": dict.fromkeys(STATS, 7)},
        "items": {"rope": 1},
        "flags": {"RAVEN"},
    }
    base.update(kw)
    return gbx.SimpleEnv(**base)  # type: ignore[arg-type]


def codes(src: str, scope: gbx.Scope) -> list[str]:
    _, diags = gbx.check_source(src, scope)
    return [d.code for d in diags if d.severity == "error"]


# ── parsing ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("2d6", Dice(2, 6)),
        ("d6", Dice(1, 6)),
        ("1 + 2 * 3", Binary("+", Num(1), Binary("*", Num(2), Num(3)))),
        ("(1 + 2) * 3", Binary("*", Binary("+", Num(1), Num(2)), Num(3))),
        ("10 - 3 - 2", Binary("-", Binary("-", Num(10), Num(3)), Num(2))),
        ("player.SKILL", Attr("player", "SKILL")),
        ("has(rope)", Call("has", (Name("rope"),))),
        ("damage", Name("damage")),
    ],
)
def test_parse(src: str, expected: gbx.Expr) -> None:
    assert gbx.parse(src) == expected


@pytest.mark.parametrize(
    ("src", "message"),
    [
        ("", "Empty expression"),
        ("1 +", "Unexpected end of expression"),
        ("(1 + 2", "Expected ')'"),
        ("1 < 2 < 3", "can't be chained"),
        ("2 $ 3", "Unexpected character"),
        ("0d6", "Dice count"),
        ("2d1", "sides"),
        ("player.", "Expected a name"),
        ("12abc", "Unexpected character"),
        ("1 2", "Unexpected '2'"),
    ],
)
def test_syntax_errors(src: str, message: str) -> None:
    with pytest.raises(gbx.GbxSyntaxError, match=re.escape(message)):
        gbx.parse(src)


def test_syntax_error_span_points_at_problem() -> None:
    with pytest.raises(gbx.GbxSyntaxError) as exc:
        gbx.parse("1 + (2 * )")
    assert exc.value.span.start == 9


def test_spans_cover_source() -> None:
    src = "has(rope) and player.GOLD >= 5"
    e = gbx.parse(src)
    assert (e.span.start, e.span.end) == (0, len(src))
    attr = next(n for n in walk(e) if isinstance(n, Attr))
    assert src[attr.attr_span.start : attr.attr_span.end] == "GOLD"


def test_too_deep_or_long() -> None:
    with pytest.raises(gbx.GbxSyntaxError, match="nested too deeply"):
        gbx.parse("(" * 100 + "1" + ")" * 100)
    with pytest.raises(gbx.GbxSyntaxError, match="longer than"):
        gbx.parse("1 + " * 1000 + "1")


@given(st.one_of(numbers, booleans))
@settings(max_examples=300)
def test_source_round_trip(e: gbx.Expr) -> None:
    assert gbx.parse(gbx.to_source(e)) == e


@given(st.one_of(numbers, booleans))
def test_json_round_trip(e: gbx.Expr) -> None:
    assert gbx.from_json(gbx.to_json(e)) == e


@given(st.text(max_size=40))
def test_parser_never_crashes(src: str) -> None:
    with contextlib.suppress(gbx.GbxSyntaxError):
        gbx.parse(src)


# ── checking ─────────────────────────────────────────────────────────────


@given(booleans)
def test_generated_conditions_typecheck(e: gbx.Expr) -> None:
    assert [d for d in gbx.check(e, COND.with_(allow_dice=True)) if d.severity == "error"] == []


@pytest.mark.parametrize(
    ("src", "code"),
    [
        ("has(sword)", "ref"),
        ("player.MAGIC >= 1", "stat"),
        ("STAMNA > 2", "name"),
        ("1d6 > 3", "dice"),
        ("SKILL + 1", "type"),
        ("has(rope) + 1 > 2", "type"),
        ("frobnicate(1) > 0", "name"),
        ("has(rope, potion)", "args"),
        ("max(1) > 0", "args"),
        ("tier >= 3", "type"),
        ("true < false", "type"),
        ("has", "name"),
        ("SKILL / 0 > 1", "div_zero"),
    ],
)
def test_condition_errors(src: str, code: str) -> None:
    assert code in codes(src, COND)


def test_suggestions() -> None:
    _, diags = gbx.check_source("STAMNA > 2", COND)
    assert "did you mean 'STAMINA'" in diags[0].message
    _, diags = gbx.check_source("player.gold > 2", COND)
    assert "did you mean 'GOLD'" in diags[0].message


@pytest.mark.parametrize(
    "src",
    [
        "has(rope) and GOLD >= 5",
        "flag(ANY_NEW_CODEWORD)",  # flags are declared by use
        "not skill(TRACKING) or class(ranger)",
        "tier >= medium",
        "visits(a1_bridge) == 0",
        "count(potion) >= 2",
        "player.SKILL + 2 > LUCK",
    ],
)
def test_valid_conditions(src: str) -> None:
    assert codes(src, COND) == []


def test_contexts() -> None:
    formula = gbx.scope_for(Context.ENEMY_FORMULA, INPUTS)
    assert codes("8 + level * 2", formula) == []
    assert "dice" in codes("level + 1d6", formula)
    assert "name" in codes("player.SKILL", formula)

    test_ok = gbx.scope_for(Context.TEST_SUCCESS, INPUTS)
    assert codes("roll <= player.LUCK", test_ok) == []

    damage = gbx.scope_for(Context.COMBAT_DAMAGE, INPUTS)
    assert codes("natural == 12 ? damage * 2 : damage", damage) == []
    assert codes("max(1, damage - target.STAMINA)", damage) == []
    # ARMOR is enemy-only here, so attacker/target can't rely on it.
    assert "stat" in codes("damage - target.ARMOR", damage)


def test_visits_is_flagged_unprintable() -> None:
    _, diags = gbx.check_source("visits(a1_bridge) > 0", COND)
    assert [d.code for d in diags] == ["unprintable"]


def test_fraction_warning_unless_rounded() -> None:
    _, diags = gbx.check_source("SKILL / 2", AMOUNT)
    assert [d.code for d in diags] == ["fraction"]
    _, diags = gbx.check_source("floor(SKILL / 2)", AMOUNT)
    assert diags == []


# ── evaluation ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("src", "value"),
    [
        ("1 + 2 * 3", 7),
        ("7 / 2", Fraction(7, 2)),
        ("floor(7 / 2)", 3),
        ("ceil(7 / 2)", 4),
        ("round(5 / 2)", 3),
        ("round(-5 / 2)", -2),
        ("-7 % 3", 2),
        ("clamp(15, 1, 10)", 10),
        ("min(3, 1, 2)", 1),
        ("abs(-4)", 4),
        ("player.SKILL + GOLD", 14),
        ("count(rope) + count(potion)", 1),
        ("true ? 1 : 2", 1),
    ],
)
def test_evaluate_numbers(src: str, value: Fraction) -> None:
    assert gbx.evaluate(gbx.parse(src), env()) == value


@pytest.mark.parametrize(
    ("src", "value"),
    [
        ("has(rope)", True),
        ("has(potion)", False),
        ("flag(RAVEN) and not flag(FIRE)", True),
        ("tier >= medium", True),
        ("tier > medium", False),
        ("tier == medium", True),
        ("SKILL >= 7 and LUCK < 7", False),
        ("false and 1 / 0 > 1", False),  # short-circuit
    ],
)
def test_evaluate_conditions(src: str, value: bool) -> None:
    assert gbx.evaluate_bool(gbx.parse(src), env()) is value


def test_evaluate_int_floors() -> None:
    assert gbx.evaluate_int(gbx.parse("-7 / 2"), env()) == -4


def test_runtime_division_by_zero() -> None:
    with pytest.raises(gbx.GbxEvalError):
        gbx.evaluate(gbx.parse("1 / (SKILL - 7)"), env())


def test_dice_are_seeded_and_recorded() -> None:
    e = gbx.parse("2d6 + 1")
    r1, r2 = gbx.SeededRng(42), gbx.SeededRng(42)
    assert [gbx.evaluate_int(e, env(), r1) for _ in range(5)] == [
        gbx.evaluate_int(e, env(), r2) for _ in range(5)
    ]
    assert len(r1.history) == 5
    assert all(c == 2 and s == 6 and len(f) == 2 for c, s, f in r1.history)
    with pytest.raises(gbx.GbxEvalError, match="random source"):
        gbx.evaluate(e, env())


@given(numbers, st.integers(0, 2**32))
@settings(max_examples=200)
def test_evaluation_total_and_within_range(e: gbx.Expr, seed: int) -> None:
    """Well-typed expressions evaluate, and land inside value_range()."""
    stat_range = (Fraction(7), Fraction(7))
    known = dict.fromkeys(STATS, stat_range)
    value = gbx.evaluate_number(e, env(), gbx.SeededRng(seed))
    bounds = gbx.value_range(e, known)
    if bounds is not None:
        assert bounds[0] <= value <= bounds[1]


@given(booleans, st.integers(0, 2**32))
def test_conditions_always_evaluate(e: gbx.Expr, seed: int) -> None:
    assert isinstance(gbx.evaluate(e, env(), gbx.SeededRng(seed)), bool)


# ── analysis ─────────────────────────────────────────────────────────────


def test_ranges() -> None:
    assert gbx.integer_range(gbx.parse("2d6")) == (2, 12)
    assert gbx.integer_range(gbx.parse("1d6 - 1d6")) == (-5, 5)
    assert gbx.integer_range(gbx.parse("2d6 + SKILL")) is None
    assert gbx.integer_range(
        gbx.parse("8 + level * 2"), {"level": (Fraction(1), Fraction(10))}
    ) == (10, 28)
    assert gbx.integer_range(gbx.parse("max(1, 1d6 - 3)")) == (1, 3)


def test_distribution() -> None:
    d = gbx.distribution(gbx.parse("2d6"))
    assert d is not None
    assert sum(d.values()) == 1
    assert d[7] == Fraction(6, 36)
    assert min(d) == 2
    assert max(d) == 12
    assert gbx.distribution(gbx.parse("1d6 + SKILL")) is None
    d3 = gbx.distribution(gbx.parse("2 * 1d4 - 1"))
    assert d3 == {1: Fraction(1, 4), 3: Fraction(1, 4), 5: Fraction(1, 4), 7: Fraction(1, 4)}


# ── references & rename ──────────────────────────────────────────────────


def test_references() -> None:
    e = gbx.parse("has(rope) and flag(RAVEN) and GOLD >= enemy.SKILL and tier >= medium")
    refs = [(r.kind, r.key, r.obj) for r in gbx.references(e, COND)]
    assert refs == [
        (RefKind.ITEM, "rope", None),
        (RefKind.FLAG, "RAVEN", None),
        (RefKind.STAT, "GOLD", "player"),
        (RefKind.STAT, "SKILL", "enemy"),
        (RefKind.TIER, "medium", None),
    ]


def test_rename_preserves_formatting() -> None:
    src = "has( rope )   and count(rope)>=2 and flag(rope)"
    out = gbx.rename_in_source(src, COND, RefKind.ITEM, "rope", "climbing_rope")
    assert out == "has( climbing_rope )   and count(climbing_rope)>=2 and flag(rope)"


def test_rename_stat_on_one_object() -> None:
    damage = gbx.scope_for(Context.COMBAT_DAMAGE, INPUTS)
    src = "player.SKILL + enemy.SKILL"
    assert (
        gbx.rename_in_source(src, damage, RefKind.STAT, "SKILL", "PROWESS", obj="enemy")
        == "player.SKILL + enemy.PROWESS"
    )
    assert gbx.rename_in_source("SKILL > 1", COND, RefKind.STAT, "SKILL", "S") == "S > 1"


def test_rename_ignores_broken_source() -> None:
    assert gbx.rename_in_source("has(rope", COND, RefKind.ITEM, "rope", "x") == "has(rope"


# ── English ──────────────────────────────────────────────────────────────


NAMES = {
    (RefKind.ITEM, "rope"): "Rope",
    (RefKind.ITEM, "potion"): "Healing Potions",
    (RefKind.STAT, "GOLD"): "Gold Crowns",
    (RefKind.TIER, "medium"): "Medium",
    (RefKind.NODE, "a1_bridge"): "the Haunted Bridge",
    (RefKind.SKILL, "TRACKING"): "Tracking",
}


def namer(kind: RefKind, key: str) -> str:
    return NAMES.get((kind, key), key)


@pytest.mark.parametrize(
    ("src", "english"),
    [
        ("has(rope)", "you have the Rope"),
        ("not has(rope)", "you do not have the Rope"),
        ("GOLD >= 5", "your Gold Crowns is at least 5"),
        ("5 > GOLD", "your Gold Crowns is less than 5"),
        ("count(potion) >= 2", "you have at least 2 Healing Potions"),
        ("flag(RAVEN)", "you have the codeword RAVEN"),
        ("skill(TRACKING) or class(ranger)", "you have the skill of Tracking or you are a ranger"),
        (
            "not (has(rope) or flag(RAVEN))",
            "you do not have the Rope and you do not have the codeword RAVEN",
        ),
        (
            "has(rope) and (flag(A) or flag(B))",
            "you have the Rope and (you have the codeword A or you have the codeword B)",
        ),
        ("tier >= medium", "you are playing at the Medium tier or higher"),
        ("visits(a1_bridge) >= 1", "you have been to the Haunted Bridge before"),
        ("visits(a1_bridge) == 0", "you have not been to the Haunted Bridge before"),
    ],
)
def test_condition_english(src: str, english: str) -> None:
    assert gbx.condition_to_english(gbx.parse(src), namer, tiers=TIERS) == english


@pytest.mark.parametrize(
    ("src", "english"),
    [
        ("2d6 + player.SKILL", "two dice plus your SKILL"),
        ("1d6", "one die"),
        ("1d20", "1d20"),
        ("floor(SKILL / 2)", "your SKILL divided by 2, rounded down"),
        ("(1d6 + 1) * 2", "(one die plus 1) times 2"),
        ("enemy.SKILL", "your opponent's SKILL"),
    ],
)
def test_number_english(src: str, english: str) -> None:
    assert gbx.number_to_english(gbx.parse(src), namer) == english


@given(booleans)
def test_english_never_crashes(e: gbx.Expr) -> None:
    assert gbx.condition_to_english(e, namer, tiers=TIERS)


# ── compiler ≡ evaluator ─────────────────────────────────────────────────


def _same(e: gbx.Expr, seed: int) -> None:
    from gamebook.core.gbx.compiler import compile_expr as compile_fn

    try:
        expected: object = gbx.evaluate(e, env(), gbx.SeededRng(seed))
    except gbx.GbxEvalError as exc:
        expected = type(exc)
    try:
        got: object = compile_fn(e)(env(), gbx.SeededRng(seed))
    except gbx.GbxEvalError as exc:
        got = type(exc)
    if isinstance(expected, Fraction) and not isinstance(got, bool):
        assert isinstance(got, int | Fraction)
        assert Fraction(got) == expected
    else:
        assert got == expected


@given(st.one_of(numbers, booleans), st.integers(0, 2**32))
@settings(max_examples=400)
def test_compiler_matches_evaluator(e: gbx.Expr, seed: int) -> None:
    _same(e, seed)


@pytest.mark.parametrize(
    "src",
    [
        "7 / 2",
        "-7 % 3",
        "7 % -2",
        "round(-5 / 2)",
        "floor(7 / 2) * 2",
        "1 / 0",
        "clamp(15, 1, 10)",
        "(1 / 3) * 3 == 1",
        "tier >= medium",
        "max(1 / 2, 1 / 3)",
        "abs(-1 / 2)",
        "true < false",
    ],
)
def test_compiler_edge_cases(src: str) -> None:
    _same(gbx.parse(src), 1)


# ── portable dice (PCG32) ────────────────────────────────────────────────

PCG_VECTORS = {
    0: ([3894649422, 2055130073, 2315086854, 2925816488, 3443325253, 1644475139], [1, 6, 1, 3, 2]),
    42: ([3270867926, 1795671209, 1924641435, 1143034755, 4121910957, 1757328946], [3, 6, 4, 4, 4]),
    2**63 + 5: (
        [3848082736, 1504244978, 3610293564, 1948130859, 1524195164, 434124324],
        [5, 3, 1, 4, 3],
    ),
}


@pytest.mark.parametrize("seed", list(PCG_VECTORS))
def test_pcg_reference_vectors(seed: int) -> None:
    """Pinned outputs: other runtimes (the TS player) must reproduce these exactly."""
    raw, dice = PCG_VECTORS[seed]
    rng = gbx.SeededRng(seed)
    assert [rng._next32() for _ in range(6)] == raw
    assert gbx.SeededRng(seed).roll(5, 6) == dice


@given(st.integers(0, 2**64 - 1), st.integers(2, 1000))
@settings(max_examples=200)
def test_bounded_rolls_in_range(seed: int, sides: int) -> None:
    faces = gbx.SeededRng(seed).roll(20, sides)
    assert all(1 <= f <= sides for f in faces)


def test_dice_are_roughly_uniform() -> None:
    rng = gbx.SeededRng(123)
    counts = [0] * 6
    for f in rng.roll(60_000, 6):
        counts[f - 1] += 1
    chi2 = sum((c - 10_000) ** 2 / 10_000 for c in counts)
    assert chi2 < 20.5  # p ≈ 0.001 for 5 degrees of freedom


def test_tokens_are_ascii_only_like_the_ts_player() -> None:
    with pytest.raises(gbx.GbxSyntaxError):
        gbx.parse("\uff11\uff12 + 1")  # fullwidth digits
    with pytest.raises(gbx.GbxSyntaxError, match=r"Unexpected character '\\x1c' \(at 3\)"):
        gbx.parse("1 +\x1c2")


def test_integer_results_are_capped_at_2_53_in_both_engines() -> None:
    from gamebook.core.gbx.compiler import compile_int

    env = gbx.SimpleEnv()
    assert compile_int(gbx.parse("9007199254740993 - 9007199254740992"))(env, None) == 1
    with pytest.raises(gbx.GbxEvalError, match="number too large"):
        compile_int(gbx.parse("9007199254740993 * 2"))(env, None)
