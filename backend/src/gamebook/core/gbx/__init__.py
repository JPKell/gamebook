"""gbx — the gamebook expression language (see docs/adr/0003-gbx-language.md).

One small, safe language for dice, stat formulas, conditions, effect amounts
and combat hooks::

    2d6 + player.SKILL
    8 + level * 2 + floor(level / 3)
    has(rope) and GOLD >= 5
    flag(RAVEN) or skill(TRACKING)
    tier >= medium and visits(a1_bridge) == 0
    natural == 12 ? damage * 2 : damage
"""

from gamebook.core.gbx.analysis import distribution, integer_range, value_range
from gamebook.core.gbx.ast import Expr, Span, from_json, to_json
from gamebook.core.gbx.checker import check, check_source, is_random
from gamebook.core.gbx.english import condition_to_english, number_to_english
from gamebook.core.gbx.errors import Diagnostic, GbxEvalError, GbxSyntaxError
from gamebook.core.gbx.evaluator import (
    Env,
    Rng,
    SeededRng,
    SimpleEnv,
    TierValue,
    evaluate,
    evaluate_bool,
    evaluate_int,
    evaluate_number,
)
from gamebook.core.gbx.parser import parse
from gamebook.core.gbx.references import Reference, references, rename_in_source
from gamebook.core.gbx.scope import Context, RefKind, Scope, ScopeInputs, scope_for
from gamebook.core.gbx.source import to_source

__all__ = [
    "Context",
    "Diagnostic",
    "Env",
    "Expr",
    "GbxEvalError",
    "GbxSyntaxError",
    "RefKind",
    "Reference",
    "Rng",
    "Scope",
    "ScopeInputs",
    "SeededRng",
    "SimpleEnv",
    "Span",
    "TierValue",
    "check",
    "check_source",
    "condition_to_english",
    "distribution",
    "evaluate",
    "evaluate_bool",
    "evaluate_int",
    "evaluate_number",
    "from_json",
    "integer_range",
    "is_random",
    "number_to_english",
    "parse",
    "references",
    "rename_in_source",
    "scope_for",
    "to_json",
    "to_source",
    "value_range",
]
