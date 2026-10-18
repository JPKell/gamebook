"""Editor support for gbx: check, normalise, explain, bound."""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.core import gbx
from gamebook.core.gbx.english import Namer
from gamebook.core.gbx.scope import Context, RefKind, ScopeInputs, scope_for
from gamebook.core.rules import RuleSystemDef, TierError, effective_tier
from gamebook.db.models import Book, Item, Node, RuleSystem, Series
from gamebook.schemas.analysis import GbxCheckIn, GbxCheckOut, GbxDiagnosticOut
from gamebook.services.common import require
from gamebook.services.errors import InvalidError
from gamebook.services.snapshot import active_rules


def _namer(
    session: Session,
    series_id: str,
    book_id: str | None,
    rules: RuleSystemDef | None,
    tier: str | None,
) -> Namer:
    items = dict(
        session.execute(select(Item.key, Item.name).where(Item.series_id == series_id)).all()
    )
    nodes = (
        dict(session.execute(select(Node.key, Node.title).where(Node.book_id == book_id)).all())
        if book_id
        else {}
    )
    stats: dict[str, str] = {}
    skills: dict[str, str] = {}
    classes: dict[str, str] = {}
    tiers: dict[str, str] = {}
    if rules is not None:
        tiers = {t.key: t.label for t in rules.tiers}
        top = tier or rules.tiers[-1].key
        try:
            eff = effective_tier(rules, top)
            stats = {k: s.label for k, s in eff.stats.items()}
            skills = {k: s.label for k, s in eff.skills.items()}
            classes = {k: c.label for k, c in eff.classes.items()}
        except TierError:
            pass
    tables = {
        RefKind.ITEM: items,
        RefKind.NODE: nodes,
        RefKind.STAT: stats,
        RefKind.SKILL: skills,
        RefKind.CLASS: classes,
        RefKind.TIER: tiers,
    }

    def name(kind: RefKind, key: str) -> str:
        return tables.get(kind, {}).get(key, key)

    return name


def check(session: Session, data: GbxCheckIn) -> GbxCheckOut:
    series_id = data.series_id
    book_id = data.book_id
    if book_id is not None:
        book = require(session, Book, book_id)
        series_id = book.series_id
    if series_id is None:
        raise InvalidError("Give a book_id or series_id", field="book_id")
    require(session, Series, series_id)

    rules = active_rules(session, series_id)
    if data.rule_system_id is not None:
        rs = require(session, RuleSystem, data.rule_system_id)
        if rs.series_id != series_id:
            raise InvalidError("That rule system belongs to another series", field="rule_system_id")
        try:
            rules = RuleSystemDef.model_validate(rs.definition)
        except ValidationError as exc:
            raise InvalidError("That rule system is invalid") from exc
    inputs = ScopeInputs(
        items=frozenset(session.scalars(select(Item.key).where(Item.series_id == series_id)))
    )
    if rules is not None:
        tier = data.tier or rules.tiers[0].key
        try:
            eff = effective_tier(rules, tier)
        except TierError as exc:
            raise InvalidError(str(exc), field="tier") from exc
        inputs = ScopeInputs(
            player_stats=eff.player_stats(),
            enemy_stats=eff.enemy_stats(),
            tiers=rules.tier_keys(),
            items=inputs.items,
            skills=frozenset(eff.skills),
            classes=frozenset(eff.classes),
            nodes=frozenset(session.scalars(select(Node.key).where(Node.book_id == book_id)))
            if book_id
            else None,
        )
    scope = scope_for(data.context, inputs)
    expr, diags = gbx.check_source(data.source, scope)
    out = GbxCheckOut(
        ok=not any(d.severity == "error" for d in diags),
        diagnostics=[
            GbxDiagnosticOut(
                severity=d.severity,
                code=d.code,
                message=d.message,
                start=d.span.start,
                end=d.span.end,
            )
            for d in diags
        ],
    )
    if expr is None:
        return out
    out.normalized = gbx.to_source(expr)
    namer = _namer(session, series_id, book_id, rules, data.tier)
    tiers = rules.tier_keys() if rules else ()
    if scope.expected == "bool":
        out.english = gbx.condition_to_english(
            expr, namer, tiers=tiers, bare_object=scope.bare_object
        )
    else:
        out.english = gbx.number_to_english(expr, namer, tiers=tiers, bare_object=scope.bare_object)
        out.range = gbx.integer_range(expr)
        dist = gbx.distribution(expr)
        if dist is not None:
            out.distribution = {k: float(v) for k, v in dist.items()}
    return out


__all__ = ["Context", "check"]
