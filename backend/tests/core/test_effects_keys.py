import pytest
from pydantic import TypeAdapter, ValidationError

from gamebook.core import gbx
from gamebook.core.effects import (
    Effect,
    effect_refs,
    effect_to_english,
    fires_once,
    rename_in_effect,
)
from gamebook.core.gbx.scope import Context, RefKind, ScopeInputs
from gamebook.core.keys import key_problem, slugify, unique_key

EFFECT = TypeAdapter(Effect)
SCOPE = gbx.scope_for(Context.AMOUNT, ScopeInputs(player_stats=frozenset({"SKILL", "GOLD"})))


def eff(**kw: object) -> Effect:
    return EFFECT.validate_python(kw)


def test_discriminated_union_and_strictness() -> None:
    assert eff(op="give", item="rope").qty == 1  # type: ignore[union-attr]
    with pytest.raises(ValidationError):
        eff(op="give", item="rope", qty=0)
    with pytest.raises(ValidationError):
        eff(op="explode")
    with pytest.raises(ValidationError):
        eff(op="set_flag", flag="X", extra=1)


def test_once_defaults() -> None:
    assert fires_once(eff(op="give", item="rope"))
    assert fires_once(eff(op="set_flag", flag="X"))
    assert not fires_once(eff(op="modify", stat="SKILL", amount="-1"))
    assert fires_once(eff(op="modify", stat="SKILL", amount="-1", once=True))
    assert not fires_once(eff(op="give", item="rope", once=False))


@pytest.mark.parametrize(
    ("raw", "english"),
    [
        ({"op": "modify", "stat": "SKILL", "amount": "2"}, "Add 2 to your SKILL."),
        ({"op": "modify", "stat": "SKILL", "amount": "-2"}, "Deduct 2 from your SKILL."),
        ({"op": "modify", "stat": "GOLD", "amount": "1d6"}, "Add one die to your GOLD."),
        ({"op": "set", "stat": "SKILL", "value": "7"}, "Set your SKILL to 7."),
        ({"op": "give", "item": "rope"}, "You gain the rope."),
        ({"op": "give", "item": "potion", "qty": 3}, "You gain 3 potion."),
        ({"op": "take", "item": "rope"}, "You lose the rope."),
        ({"op": "set_flag", "flag": "RAVEN"}, "Note the codeword RAVEN."),
        ({"op": "clear_flag", "flag": "RAVEN"}, "Cross out the codeword RAVEN."),
        ({"op": "learn", "skill": "TRACKING"}, "You learn the skill of TRACKING."),
        ({"op": "give", "item": "rope", "print_text": "Take the rope."}, "Take the rope."),
    ],
)
def test_effect_english(raw: dict[str, object], english: str) -> None:
    assert effect_to_english(EFFECT.validate_python(raw)) == english


def test_effect_refs_and_rename() -> None:
    e = eff(op="modify", stat="GOLD", amount="count(rope) * 2", min_tier="medium")
    assert effect_refs(e, SCOPE) == [
        (RefKind.STAT, "GOLD", "effect.modify"),
        (RefKind.ITEM, "rope", "effect.modify"),
        (RefKind.TIER, "medium", "effect.modify"),
    ]
    renamed = rename_in_effect(e, SCOPE, RefKind.ITEM, "rope", "cord")
    assert renamed.amount == "count(cord) * 2"  # type: ignore[union-attr]
    given = rename_in_effect(eff(op="give", item="rope"), SCOPE, RefKind.ITEM, "rope", "cord")
    assert given.model_dump()["item"] == "cord"
    assert rename_in_effect(e, SCOPE, RefKind.TIER, "medium", "mid").min_tier == "mid"


@pytest.mark.parametrize(
    ("key", "ok"),
    [
        ("a1_bridge", True),
        ("RAVEN", True),
        ("1abc", False),
        ("a-b", False),
        ("d6", False),
        ("tier", False),
        ("x" * 65, False),
    ],
)
def test_key_rules(key: str, ok: bool) -> None:
    assert (key_problem(key) is None) is ok


def test_slugify_and_unique() -> None:
    assert slugify("The Haunted Bridge!") == "the_haunted_bridge"
    assert slugify("42 Steps") == "untitled_42_steps"
    assert slugify("") == "untitled"
    assert slugify("D6") == "untitled_d6"
    assert unique_key("orc", {"orc", "orc_2"}) == "orc_3"
    assert unique_key("orc", set()) == "orc"
