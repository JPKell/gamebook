"""Book and rule-system validation (SPEC §7).

Expressions are checked against the scope of the tier they apply at (the
element's ``min_tier``, else the lowest tier). If something only exists in a
higher tier, that's a warning suggesting a ``min_tier`` rather than an error.
"""

from __future__ import annotations

import itertools
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

from gamebook.core import gbx
from gamebook.core.analysis.digest import compute as compute_digest
from gamebook.core.analysis.graph import reachable, reverse, successors
from gamebook.core.analysis.problems import SEVERITY_ORDER, Problem
from gamebook.core.effects import (
    ClearFlag,
    Effect,
    EquipItem,
    GiveItem,
    LearnSkill,
    ModifyStat,
    SetFlag,
    SetStat,
    TakeItem,
)
from gamebook.core.gbx.scope import Context, RefKind, Scope, ScopeInputs, scope_for
from gamebook.core.model import OUTCOME_KEYS, BookSnapshot, Choice, Node
from gamebook.core.rules.schema import (
    EffectiveTier,
    RuleSystemDef,
    StartingItem,
    StatBonus,
    TierError,
    effective_tier,
)

# ── scopes ───────────────────────────────────────────────────────────────


class _Scopes:
    """Scope cache per (context, tier) for one book."""

    def __init__(self, book: BookSnapshot, rules: RuleSystemDef) -> None:
        self.rules = rules
        self.tiers = rules.tier_keys()
        self.effective: dict[str, EffectiveTier] = {}
        for t in self.tiers:
            try:
                self.effective[t] = effective_tier(rules, t)
            except TierError:
                continue
        self.items = frozenset(i.key for i in book.items if book.available(i))
        self.nodes = frozenset(n.key for n in book.nodes)
        self._cache: dict[tuple[Context, str], Scope] = {}

    @property
    def base(self) -> str:
        return self.tiers[0]

    @property
    def top(self) -> str:
        return self.tiers[-1]

    def get(self, context: Context, tier: str | None) -> Scope:
        tier = tier if tier in self.effective else self.base
        key = (context, tier)
        if key not in self._cache:
            eff = self.effective.get(tier)
            inputs = ScopeInputs(
                player_stats=eff.player_stats() if eff else frozenset(),
                enemy_stats=eff.enemy_stats() if eff else frozenset(),
                tiers=self.tiers,
                items=self.items,
                skills=frozenset(eff.skills) if eff else frozenset(),
                classes=frozenset(eff.classes) if eff else frozenset(),
                nodes=self.nodes,
            )
            self._cache[key] = scope_for(context, inputs)
        return self._cache[key]

    def tier_label(self, tier: str) -> str:
        eff = self.effective.get(tier)
        return eff.label if eff else tier


# ── collector ────────────────────────────────────────────────────────────


@dataclass
class _Ctx:
    """Where a problem is, for building Problem rows."""

    act_id: str | None = None
    node_id: str | None = None
    choice_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None


@dataclass
class _Collector:
    scopes: _Scopes | None
    problems: list[Problem] = field(default_factory=list)
    flags_tested: dict[str, list[_Ctx]] = field(default_factory=dict)
    flags_set: set[str] = field(default_factory=set)

    def add(self, sev: str, code: str, msg: str, ctx: _Ctx, field_: str | None = None) -> None:
        self.problems.append(
            Problem(
                severity=sev,  # type: ignore[arg-type]
                code=code,
                message=msg,
                act_id=ctx.act_id,
                node_id=ctx.node_id,
                choice_id=ctx.choice_id,
                entity_type=ctx.entity_type,
                entity_id=ctx.entity_id,
                field=field_,
            )
        )

    def expr(
        self,
        src: str | None,
        context: Context,
        tier: str | None,
        where: str,
        ctx: _Ctx,
        field_: str,
    ) -> gbx.Expr | None:
        """Check one expression; returns the parsed AST if it parsed."""
        if src is None or self.scopes is None:
            return None
        if not src.strip():
            self.add("error", "gbx", f"{where} is empty", ctx, field_)
            return None
        sc = self.scopes
        scope = sc.get(context, tier)
        expr, diags = gbx.check_source(src, scope)
        errors = [d for d in diags if d.severity == "error"]
        effective_tier = tier if tier in sc.effective else sc.base
        if errors and expr is not None and effective_tier != sc.top:
            higher = next(
                (
                    t
                    for t in sc.tiers[sc.tiers.index(effective_tier) + 1 :]
                    if not [d for d in gbx.check(expr, sc.get(context, t)) if d.severity == "error"]
                ),
                None,
            )
            if higher is not None:
                self.add(
                    "warning",
                    "tier_scope",
                    f"{where} uses rules that only exist from the {sc.tier_label(higher)} tier; "
                    f"set its minimum tier to {sc.tier_label(higher)}",
                    ctx,
                    field_,
                )
                errors = []
                diags = [d for d in diags if d.severity != "error"]
        for d in diags:
            self.add(d.severity, f"gbx.{d.code}", f"{where}: {d.message}", ctx, field_)
        if expr is not None:
            for ref in gbx.references(expr, scope):
                if ref.kind == RefKind.FLAG:
                    self.flags_tested.setdefault(ref.key, []).append(ctx)
        return expr

    def effects(
        self, effects: Sequence[Effect], tier: str | None, where: str, ctx: _Ctx, field_: str
    ) -> None:
        if self.scopes is None:
            return
        sc = self.scopes
        for i, eff in enumerate(effects):
            f = f"{field_}[{i}]"
            label = f"{where} effect {i + 1}"
            eff_tier = eff.min_tier or tier
            if eff.min_tier and eff.min_tier not in sc.tiers:
                self.add("error", "unknown_tier", f"{label}: unknown tier {eff.min_tier!r}", ctx, f)
                eff_tier = tier
            scope = sc.get(Context.AMOUNT, eff_tier)
            match eff:
                case ModifyStat(stat=s, amount=src) | SetStat(stat=s, value=src):
                    self._stat(s, scope, eff_tier, label, ctx, f)
                    self.expr(src, Context.AMOUNT, eff_tier, label, ctx, f)
                case GiveItem(item=k) | TakeItem(item=k) | EquipItem(item=k):
                    if k not in sc.items:
                        self.add("error", "unknown_item", f"{label}: unknown item {k!r}", ctx, f)
                case SetFlag(flag=k):
                    self.flags_set.add(k)
                case ClearFlag():
                    pass
                case LearnSkill(skill=k):
                    eff_def = sc.effective.get(eff_tier or sc.base)
                    if eff_def is None or k not in eff_def.skills:
                        known_anywhere = any(k in e.skills for e in sc.effective.values())
                        sev, msg = (
                            ("warning", f"{label}: skill {k!r} only exists in higher tiers")
                            if known_anywhere
                            else ("error", f"{label}: unknown skill {k!r}")
                        )
                        self.add(sev, "unknown_skill", msg, ctx, f)

    def _stat(
        self, stat: str, scope: Scope, tier: str | None, label: str, ctx: _Ctx, f: str
    ) -> None:
        assert self.scopes is not None
        if stat in scope.objects.get("player", frozenset()):
            return
        anywhere = any(stat in e.player_stats() for e in self.scopes.effective.values())
        if anywhere:
            self.add(
                "warning",
                "tier_scope",
                f"{label}: {stat} only exists in higher tiers; set a minimum tier",
                ctx,
                f,
            )
        else:
            self.add("error", "unknown_stat", f"{label}: unknown stat {stat!r}", ctx, f)


# ── entry points ─────────────────────────────────────────────────────────


def validate_book(book: BookSnapshot) -> list[Problem]:
    rules = book.rules
    rule_problems = (
        validate_rule_system(rules, items=frozenset(i.key for i in book.items if book.available(i)))
        if rules is not None
        else []
    )
    scopes = _Scopes(book, rules) if rules is not None and rules.tiers else None
    col = _Collector(scopes)
    if rules is None:
        col.add("error", "no_rules", "The series has no active rule system", _Ctx())

    _check_structure(book, col)
    for node in book.nodes:
        _check_node(book, node, col)
    _check_entities(book, col)
    _check_flags(book, col)
    _check_digest(book, col)
    _check_beats(book, col)

    problems = rule_problems + col.problems
    return sorted(problems, key=lambda p: SEVERITY_ORDER[p.severity])


def _tier_ok(tier: str | None, col: _Collector, ctx: _Ctx, what: str, field_: str) -> str | None:
    if tier is None or col.scopes is None:
        return tier
    if tier not in col.scopes.tiers:
        col.add("error", "unknown_tier", f"{what}: unknown tier {tier!r}", ctx, field_)
        return None
    return tier


# ── structure ────────────────────────────────────────────────────────────


def _check_structure(book: BookSnapshot, col: _Collector) -> None:
    acts = sorted(book.acts, key=lambda a: a.position)
    act_idx = book.act_index()
    by_act: dict[str, list[Node]] = {a.id: [] for a in acts}
    for n in book.nodes:
        by_act.setdefault(n.act_id, []).append(n)

    if not book.nodes:
        return

    if book.start_node_id is None or book.node(book.start_node_id) is None:
        col.add("error", "no_start", "The book has no start node", _Ctx())
    else:
        start = book.node(book.start_node_id)
        assert start is not None
        if acts and act_idx.get(start.act_id) != 0:
            col.add(
                "warning",
                "start_not_first_act",
                f"The start node '{start.title}' is not in the first act",
                _Ctx(act_id=start.act_id, node_id=start.id),
            )

    last = len(acts) - 1
    for i, act in enumerate(acts):
        nodes = by_act.get(act.id, [])
        ctx = _Ctx(act_id=act.id)
        if i < last and not any(n.is_act_exit for n in nodes):
            col.add("error", "act_no_exit", f"{act.title} has no exit node", ctx)
        if i > 0 and not any(n.is_act_entry for n in nodes):
            col.add("error", "act_no_entry", f"{act.title} has no entry node", ctx)
        if i == last:
            for n in nodes:
                if n.is_act_exit:
                    col.add(
                        "warning",
                        "exit_in_final_act",
                        f"'{n.title}' is an act exit, but {act.title} is the final act",
                        _Ctx(act_id=act.id, node_id=n.id),
                    )

    nodes_by_id = {n.id: n for n in book.nodes}
    incoming_from_prev: set[str] = set()
    for n in book.nodes:
        src_i = act_idx.get(n.act_id)
        crosses_forward = False
        for c in n.choices:
            for o in c.outcomes:
                tgt = nodes_by_id.get(o.target_id) if o.target_id else None
                if tgt is None or tgt.act_id == n.act_id:
                    continue
                tgt_i = act_idx.get(tgt.act_id)
                ctx = _Ctx(act_id=n.act_id, node_id=n.id, choice_id=c.id)
                if src_i is None or tgt_i is None:
                    continue
                if tgt_i == src_i + 1 and n.is_act_exit and tgt.is_act_entry:
                    crosses_forward = True
                    incoming_from_prev.add(tgt.id)
                elif tgt_i == src_i + 1:
                    missing = []
                    if not n.is_act_exit:
                        missing.append(f"'{n.title}' is not marked as an act exit")
                    if not tgt.is_act_entry:
                        missing.append(f"'{tgt.title}' is not marked as an act entry")
                    col.add(
                        "error",
                        "act_boundary",
                        f"Choice '{c.label}' crosses into the next act, but "
                        + " and ".join(missing),
                        ctx,
                    )
                elif tgt_i < src_i:
                    col.add(
                        "error",
                        "act_backwards",
                        f"Choice '{c.label}' goes back to an earlier act",
                        ctx,
                    )
                else:
                    col.add(
                        "error",
                        "act_skip",
                        f"Choice '{c.label}' skips ahead past the next act",
                        ctx,
                    )
        if n.is_act_exit and src_i is not None and src_i < len(acts) - 1 and not crosses_forward:
            col.add(
                "warning",
                "exit_unlinked",
                f"Exit node '{n.title}' has no choice leading into the next act",
                _Ctx(act_id=n.act_id, node_id=n.id),
            )
    for n in book.nodes:
        if n.is_act_entry and act_idx.get(n.act_id, 0) > 0 and n.id not in incoming_from_prev:
            col.add(
                "warning",
                "entry_unlinked",
                f"Entry node '{n.title}' isn't reached from the previous act",
                _Ctx(act_id=n.act_id, node_id=n.id),
            )

    # Reachability (conditions ignored, so this finds definitely-unreachable content).
    adj = successors(book)
    if book.start_node_id in adj:
        reached = reachable(adj, [book.start_node_id])
        for n in book.nodes:
            if n.id not in reached:
                col.add(
                    "warning",
                    "unreachable",
                    f"'{n.title}' can't be reached from the start",
                    _Ctx(act_id=n.act_id, node_id=n.id),
                )
    endings = [n.id for n in book.nodes if n.ending_kind is not None]
    if not endings:
        col.add("warning", "no_endings", "The book has no ending nodes yet", _Ctx())
    else:
        can_end = reachable(reverse(adj), endings)
        for n in book.nodes:
            if n.id not in can_end:
                col.add(
                    "warning",
                    "no_ending",
                    f"No ending can be reached from '{n.title}'",
                    _Ctx(act_id=n.act_id, node_id=n.id),
                )

    pins = Counter(n.section_pin for n in book.nodes if n.section_pin is not None)
    for n in book.nodes:
        if n.section_pin is not None and pins[n.section_pin] > 1:
            col.add(
                "error",
                "duplicate_pin",
                f"Section number {n.section_pin} is pinned to more than one node",
                _Ctx(act_id=n.act_id, node_id=n.id),
                "section_pin",
            )
        if n.section_pin is not None and n.section_pin < 1:
            col.add(
                "error",
                "bad_pin",
                "Section numbers start at 1",
                _Ctx(act_id=n.act_id, node_id=n.id),
                "section_pin",
            )


# ── nodes ────────────────────────────────────────────────────────────────


def _check_node(book: BookSnapshot, node: Node, col: _Collector) -> None:
    ctx = _Ctx(act_id=node.act_id, node_id=node.id)
    name = f"'{node.title}'"

    if node.ending_kind is not None and node.choices:
        col.add("warning", "ending_has_choices", f"Ending {name} has choices", ctx)
    if node.ending_kind is None and not node.choices:
        col.add(
            "warning",
            "dead_end",
            f"{name} has no choices and isn't marked as an ending",
            ctx,
        )

    unconditional = [v for v in node.variants if not v.condition]
    if not unconditional:
        col.add(
            "warning",
            "no_default_variant",
            f"{name} has no unconditional text variant, so some readers may see no text",
            ctx,
        )
    elif len(unconditional) > 1:
        col.add(
            "warning",
            "shadowed_variant",
            f"{name} has {len(unconditional)} unconditional text variants; "
            "only the highest-priority one can show",
            ctx,
        )
    for i, v in enumerate(node.variants):
        col.expr(
            v.condition,
            Context.CONDITION,
            None,
            f"Text variant '{v.label}' condition",
            ctx,
            f"variants[{i}].condition",
        )

    col.effects(node.on_enter, None, f"{name} on-entry", ctx, "on_enter")

    for c in node.choices:
        _check_choice(book, node, c, col)

    enemies = {e.id: e for e in book.enemies}
    tables = {t.id: t for t in book.tables}
    for enc in node.encounters:
        ectx = _Ctx(act_id=node.act_id, node_id=node.id)
        if enc.mode == "fixed":
            if not enc.enemies:
                col.add("error", "empty_encounter", f"Encounter '{enc.label}' has no enemies", ectx)
            for ee in enc.enemies:
                enemy = enemies.get(ee.enemy_id)
                if enemy is None or not book.available(enemy):
                    col.add(
                        "error",
                        "unknown_enemy",
                        f"Encounter '{enc.label}' uses an enemy not available in this book",
                        ectx,
                    )
                if ee.level < 1 or ee.count < 1:
                    col.add(
                        "error",
                        "bad_encounter",
                        f"Encounter '{enc.label}' needs level and count of at least 1",
                        ectx,
                    )
        else:
            table = tables.get(enc.table_id) if enc.table_id else None
            if table is None or not book.available(table):
                col.add(
                    "error",
                    "unknown_table",
                    f"Encounter '{enc.label}' needs a random table available in this book",
                    ectx,
                )

    items = {i.id: i for i in book.items}
    for p in node.items:
        item = items.get(p.item_id)
        if item is None or not book.available(item):
            col.add(
                "error", "unknown_item", f"{name} places an item not available in this book", ctx
            )
    for s in node.shop or ():
        item = items.get(s.item_id)
        if item is None or not book.available(item):
            col.add("error", "unknown_item", f"{name}'s shop sells an item not available here", ctx)
        if s.price < 0:
            col.add("error", "bad_price", f"{name}'s shop has a negative price", ctx)


def _check_choice(book: BookSnapshot, node: Node, c: Choice, col: _Collector) -> None:
    ctx = _Ctx(act_id=node.act_id, node_id=node.id, choice_id=c.id)
    what = f"Choice '{c.label}'"
    tier = _tier_ok(c.min_tier, col, ctx, what, "min_tier")

    if not c.label.strip():
        col.add("warning", "empty_label", f"A choice on '{node.title}' has no text", ctx, "label")
    col.expr(c.condition, Context.CONDITION, tier, f"{what} condition", ctx, "condition")
    col.effects(c.effects, tier, what, ctx, "effects")

    keys = [o.key for o in c.outcomes]
    for o in c.outcomes:
        if o.target_id is None:
            col.add(
                "error", "outcome_no_target", f"{what}: outcome '{o.key}' has no destination", ctx
            )
        elif book.node(o.target_id) is None:
            col.add(
                "error",
                "outcome_bad_target",
                f"{what}: outcome '{o.key}' points to a missing node",
                ctx,
            )
    for k, n in Counter(keys).items():
        if n > 1:
            col.add("error", "duplicate_outcome", f"{what}: outcome '{k}' appears {n} times", ctx)

    expected = OUTCOME_KEYS[c.kind]
    if c.kind == "goto":
        if keys != ["default"]:
            col.add("error", "outcomes", f"{what} needs exactly one destination", ctx)
    elif c.kind == "test":
        _require_outcomes(what, keys, ("success", "failure"), expected, col, ctx)
        if col.scopes is not None:
            sc = col.scopes
            eff = sc.effective.get(tier or sc.base)
            if not c.test:
                col.add("error", "no_test", f"{what} doesn't say which test to roll", ctx, "test")
            elif eff is None or c.test not in eff.tests:
                anywhere = any(c.test in e.tests for e in sc.effective.values())
                sev = "warning" if anywhere else "error"
                msg = (
                    f"{what}: test '{c.test}' only exists in higher tiers; set a minimum tier"
                    if anywhere
                    else f"{what}: unknown test '{c.test}'"
                )
                col.add(sev, "unknown_test", msg, ctx, "test")
    elif c.kind == "combat":
        required = ("win", "lose", "flee") if c.flee_allowed else ("win", "lose")
        _require_outcomes(what, keys, required, expected, col, ctx)
        if not c.flee_allowed and "flee" in keys:
            col.add(
                "warning",
                "flee_unused",
                f"{what} has a flee outcome but fleeing isn't allowed",
                ctx,
            )
        if c.encounter_id is None or c.encounter_id not in {e.id for e in node.encounters}:
            col.add(
                "error",
                "combat_no_encounter",
                f"{what} must fight one of this node's encounters",
                ctx,
                "encounter_id",
            )
    elif c.kind == "roll":
        _check_roll(c, col, ctx, what, tier)


def _require_outcomes(
    what: str,
    keys: list[str],
    required: Iterable[str],
    allowed: Iterable[str],
    col: _Collector,
    ctx: _Ctx,
) -> None:
    missing = [k for k in required if k not in keys]
    unknown = [k for k in keys if k not in allowed]
    if missing:
        col.add("error", "outcomes", f"{what} needs outcome(s): {', '.join(missing)}", ctx)
    if unknown:
        col.add("error", "outcomes", f"{what} has unexpected outcome(s): {', '.join(unknown)}", ctx)


def _check_roll(c: Choice, col: _Collector, ctx: _Ctx, what: str, tier: str | None) -> None:
    if not c.dice:
        col.add("error", "no_dice", f"{what} doesn't say what to roll", ctx, "dice")
        return
    expr = col.expr(c.dice, Context.ROLL, tier, f"{what} dice", ctx, "dice")
    if not c.outcomes:
        col.add("error", "outcomes", f"{what} has no outcomes", ctx)
        return
    ranges: list[tuple[int, int, str]] = []
    for o in c.outcomes:
        if o.range_lo is None or o.range_hi is None:
            col.add("error", "roll_range", f"{what}: outcome '{o.key}' needs a range", ctx)
        elif o.range_lo > o.range_hi:
            col.add("error", "roll_range", f"{what}: outcome '{o.key}' range is backwards", ctx)
        else:
            ranges.append((o.range_lo, o.range_hi, o.key))
    if expr is None:
        return
    bounds = gbx.integer_range(expr)
    if bounds is None:
        col.add(
            "info",
            "roll_unbounded",
            f"{what}: can't verify the ranges cover every possible roll",
            ctx,
        )
        return
    gaps, overlaps = _coverage(bounds, ranges)
    if gaps:
        col.add("error", "roll_gap", f"{what}: no outcome for rolls of {_fmt_ranges(gaps)}", ctx)
    if overlaps:
        col.add(
            "error",
            "roll_overlap",
            f"{what}: several outcomes for rolls of {_fmt_ranges(overlaps)}",
            ctx,
        )
    lo, hi = bounds
    for r_lo, r_hi, key in ranges:
        if r_hi < lo or r_lo > hi:
            col.add(
                "warning",
                "roll_impossible",
                f"{what}: outcome '{key}' can never be rolled ({lo}-{hi} possible)",
                ctx,
            )


Runs = list[tuple[int, int]]


def _coverage(bounds: tuple[int, int], ranges: list[tuple[int, int, str]]) -> tuple[Runs, Runs]:
    """Uncovered and multiply-covered runs of ``bounds`` (inclusive).

    Sweeps range endpoints, so cost depends on the number of ranges, not on
    how wide the dice range is.
    """
    lo, hi = bounds
    clipped = [(max(a, lo), min(b, hi)) for a, b, _ in ranges if a <= b and b >= lo and a <= hi]
    cuts = sorted({lo, hi + 1} | {a for a, _ in clipped} | {b + 1 for _, b in clipped})
    gaps: Runs = []
    overlaps: Runs = []
    for start, nxt in itertools.pairwise(cuts):
        if start > hi:
            break
        hits = sum(1 for a, b in clipped if a <= start <= b)
        bucket = gaps if hits == 0 else overlaps if hits > 1 else None
        if bucket is None:
            continue
        if bucket and bucket[-1][1] == start - 1:
            bucket[-1] = (bucket[-1][0], nxt - 1)
        else:
            bucket.append((start, nxt - 1))
    return gaps, overlaps


def _fmt_ranges(runs: Runs) -> str:
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in runs)


# ── entities ─────────────────────────────────────────────────────────────


def _check_entities(book: BookSnapshot, col: _Collector) -> None:
    sc = col.scopes
    for enemy in book.enemies:
        if not book.available(enemy):
            continue
        ctx = _Ctx(entity_type="enemy", entity_id=enemy.id)
        if sc is None:
            continue
        needed: dict[str, str] = {}
        for t in sc.tiers:
            eff = sc.effective.get(t)
            for s in sorted(eff.enemy_stats()) if eff else ():
                needed.setdefault(s, t)
        for stat, tier in needed.items():
            if stat not in enemy.stat_formulas:
                col.add(
                    "error",
                    "enemy_missing_stat",
                    f"Enemy '{enemy.name}' needs a {stat} formula (used from the "
                    f"{sc.tier_label(tier)} tier)",
                    ctx,
                    f"stat_formulas.{stat}",
                )
        for stat, src in enemy.stat_formulas.items():
            if stat not in needed:
                col.add(
                    "warning",
                    "enemy_unused_stat",
                    f"Enemy '{enemy.name}' has a {stat} formula but no tier gives enemies {stat}",
                    ctx,
                    f"stat_formulas.{stat}",
                )
            col.expr(
                src,
                Context.ENEMY_FORMULA,
                None,
                f"Enemy '{enemy.name}' {stat}",
                ctx,
                f"stat_formulas.{stat}",
            )

    for item in book.items:
        if not book.available(item):
            continue
        ctx = _Ctx(entity_type="item", entity_id=item.id)
        if sc is None:
            continue
        for i, m in enumerate(item.modifiers):
            f = f"modifiers[{i}]"
            mod_tier = _tier_ok(m.min_tier, col, ctx, f"Item '{item.name}' modifier", f)
            label = f"Item '{item.name}' modifier"
            col._stat(m.stat, sc.get(Context.AMOUNT, mod_tier), mod_tier, label, ctx, f)
            col.expr(m.amount, Context.AMOUNT, mod_tier, label, ctx, f)
        col.effects(item.use_effects, None, f"Item '{item.name}' use", ctx, "use_effects")

    enemy_keys = {e.key for e in book.enemies if book.available(e)}
    for table in book.tables:
        if not book.available(table):
            continue
        ctx = _Ctx(entity_type="table", entity_id=table.id)
        what = f"Table '{table.name}'"
        expr = col.expr(table.dice, Context.ROLL, None, f"{what} dice", ctx, "dice")
        ranges = [(e.lo, e.hi, str(i + 1)) for i, e in enumerate(table.entries)]
        for i, e in enumerate(table.entries):
            if e.lo > e.hi:
                col.add("error", "table_range", f"{what}: entry {i + 1} range is backwards", ctx)
            if e.kind == "enemies":
                if not e.enemies:
                    col.add("error", "table_entry", f"{what}: entry {i + 1} has no enemies", ctx)
                for key, _, _ in e.enemies:
                    if key not in enemy_keys:
                        col.add("error", "unknown_enemy", f"{what}: unknown enemy {key!r}", ctx)
            elif e.kind == "item" and (
                e.item is None or (sc is not None and e.item not in sc.items)
            ):
                col.add("error", "unknown_item", f"{what}: entry {i + 1} has an unknown item", ctx)
            elif e.kind == "gold":
                col.expr(
                    e.amount or "",
                    Context.AMOUNT,
                    None,
                    f"{what} entry {i + 1}",
                    ctx,
                    f"entries[{i}].amount",
                )
        bounds = gbx.integer_range(expr) if expr is not None else None
        if bounds is not None and ranges:
            gaps, overlaps = _coverage(bounds, ranges)
            if gaps:
                col.add(
                    "error", "table_gap", f"{what}: no entry for rolls of {_fmt_ranges(gaps)}", ctx
                )
            if overlaps:
                col.add(
                    "error",
                    "table_overlap",
                    f"{what}: several entries for rolls of {_fmt_ranges(overlaps)}",
                    ctx,
                )
        elif not ranges:
            col.add("warning", "table_empty", f"{what} has no entries", ctx)


def _check_flags(book: BookSnapshot, col: _Collector) -> None:
    set_anywhere = col.flags_set | book.series_flags_set
    for flag, places in sorted(col.flags_tested.items()):
        if flag not in set_anywhere:
            ctx = places[0]
            col.add(
                "warning",
                "flag_never_set",
                f"Codeword {flag} is checked but never given anywhere in the series",
                ctx,
            )


# ── outline ──────────────────────────────────────────────────────────────


def _check_beats(book: BookSnapshot, col: _Collector) -> None:
    """Only acts that have an outline are checked, so books without one stay quiet."""
    in_beat: set[tuple[str, str]] = set()  # (act, node): a beat only covers its own act
    outlined: set[str] = set()
    nodes = {n.id for n in book.nodes}
    for beat in book.beats:
        outlined.add(beat.act_id)
        linked = [n for n in beat.node_ids if n in nodes]
        in_beat.update((beat.act_id, n) for n in linked)
        if not linked:
            col.add(
                "info",
                "beat_empty",
                f"Story beat '{beat.title}' isn't linked to any node yet",
                _Ctx(act_id=beat.act_id),
            )
    for n in book.nodes:
        if n.act_id in outlined and (n.act_id, n.id) not in in_beat:
            col.add(
                "info",
                "node_no_beat",
                f"'{n.title}' isn't part of any story beat in its act's outline",
                _Ctx(act_id=n.act_id, node_id=n.id),
            )


# ── state digest ─────────────────────────────────────────────────────────


def _check_digest(book: BookSnapshot, col: _Collector) -> None:
    """Rules that need the state digest (run at the highest tier, where every choice exists)."""
    if book.rules is None or not book.rules.tiers or book.start_node_id is None:
        return
    try:
        d = compute_digest(book)
    except TierError:
        return  # broken tiers are reported by the rule-system checks
    by_id = {n.id: n for n in book.nodes}
    for n in book.nodes:
        nd = d.nodes[n.id]
        if not nd.reachable:
            continue
        for c in n.choices:
            verdict = nd.gates.get(c.id)
            ctx = _Ctx(act_id=n.act_id, node_id=n.id, choice_id=c.id)
            label = c.label or "(unlabelled)"
            if verdict is False:
                col.add(
                    "warning",
                    "gate_never",
                    f"Choice '{label}' in '{n.title}' can never be taken: no path here meets "
                    f"'{c.condition}'",
                    ctx,
                    "condition",
                )
            elif verdict is True:
                col.add(
                    "info",
                    "gate_always",
                    f"Choice '{label}' in '{n.title}' is always available: every path here "
                    f"meets '{c.condition}'",
                    ctx,
                    "condition",
                )

    adj = successors(book)
    structural = reachable(adj, [book.start_node_id]) if book.start_node_id in adj else set()
    for n in book.nodes:
        if n.id in structural and not d.nodes[n.id].reachable:
            col.add(
                "warning",
                "unreachable_gated",
                f"'{n.title}' can only be reached through choices no reader can take",
                _Ctx(act_id=n.act_id, node_id=n.id),
            )

    # Trapped: an ending is reachable on paper, but only through never-satisfiable gates.
    # Reported where readers first get stuck (not at every node upstream of it).
    endings = [n.id for n in book.nodes if n.ending_kind is not None]
    if endings:
        live: dict[str, set[str]] = {n.id: set() for n in book.nodes}
        for n in book.nodes:
            for c in n.choices:
                if d.nodes[n.id].gates.get(c.id) is False:
                    continue
                for o in c.outcomes:
                    if o.target_id in live:
                        live[n.id].add(o.target_id)
        can_end_live = reachable(reverse(live), endings)
        can_end = reachable(reverse(adj), endings)
        trapped = {
            n.id
            for n in book.nodes
            if d.nodes[n.id].reachable and n.id in can_end and n.id not in can_end_live
        }
        preds_live = reverse(live)
        for n in book.nodes:
            if n.id in trapped and not (preds_live.get(n.id, set()) & trapped):
                col.add(
                    "warning",
                    "trapped",
                    f"Readers at '{n.title}' can get trapped: every route to an ending passes a "
                    "choice no reader can take",
                    _Ctx(act_id=n.act_id, node_id=n.id),
                )

    # Canonical predecessor overrides must be real predecessors.
    preds = reverse(successors(book))
    for n in book.nodes:
        p = n.canonical_predecessor_id
        if p is not None and p not in preds.get(n.id, set()):
            col.add(
                "warning",
                "bad_canonical",
                f"The canonical predecessor of '{n.title}' "
                f"('{by_id[p].title if p in by_id else 'deleted'}') has no choice leading here",
                _Ctx(act_id=n.act_id, node_id=n.id),
                "canonical_predecessor_id",
            )


# ── rule system ──────────────────────────────────────────────────────────


def validate_rule_system(
    rules: RuleSystemDef, *, items: frozenset[str] | None = None
) -> list[Problem]:
    """Check a rule system; ``items`` (a book's item keys) also checks starting gear."""
    col = _Collector(None)

    def ctx() -> _Ctx:
        return _Ctx(entity_type="rule_system")

    keys = [t.key for t in rules.tiers]
    for k, n in Counter(keys).items():
        if n > 1:
            col.add("error", "duplicate_tier", f"Tier '{k}' is defined {n} times", ctx())
    for i, t in enumerate(rules.tiers):
        if t.parent is not None and t.parent in keys and keys.index(t.parent) > i:
            col.add(
                "error",
                "tier_order",
                f"Tier '{t.key}' must come after its parent '{t.parent}'",
                ctx(),
            )
        for kind, defs in (
            ("stat", t.stats),
            ("test", t.tests),
            ("skill", t.skills),
            ("class", t.classes),
        ):
            for k, n in Counter(d.key for d in defs).items():
                if n > 1:
                    col.add(
                        "error",
                        f"duplicate_{kind}",
                        f"Tier '{t.key}' defines {kind} '{k}' twice",
                        ctx(),
                    )

    for t in rules.tiers:
        try:
            eff = effective_tier(rules, t.key)
        except TierError as exc:
            col.add("error", "tier_chain", str(exc), ctx())
            continue
        inputs = ScopeInputs(
            player_stats=eff.player_stats(),
            enemy_stats=eff.enemy_stats(),
            tiers=tuple(keys),
            skills=frozenset(eff.skills),
            classes=frozenset(eff.classes),
            items=None,
            nodes=None,
        )

        def check(
            src: str | None,
            context: Context,
            where: str,
            field_: str,
            inputs: ScopeInputs = inputs,
        ) -> None:
            if src is None:
                return
            _, diags = gbx.check_source(src, scope_for(context, inputs))
            for d in diags:
                col.add(d.severity, f"gbx.{d.code}", f"{where}: {d.message}", ctx(), field_)

        p = f"{eff.label} tier"
        for s in t.stats:
            if "player" in s.applies_to:
                check(
                    s.initial,
                    Context.STAT_INITIAL,
                    f"{p} {s.key} starting value",
                    f"tiers.{t.key}.stats.{s.key}",
                )
            if s.min is not None and s.max is not None and s.min > s.max:
                col.add("error", "stat_bounds", f"{p} {s.key}: minimum is above maximum", ctx())
            if not s.applies_to:
                col.add("warning", "stat_unused", f"{p} {s.key} applies to nobody", ctx())
        for test in t.tests:
            f = f"tiers.{t.key}.tests.{test.key}"
            check(test.roll, Context.TEST_ROLL, f"{p} test '{test.label}' roll", f)
            check(test.success, Context.TEST_SUCCESS, f"{p} test '{test.label}' success", f)
        player_stats = eff.player_stats()

        def bonuses(
            bs: list[StatBonus],
            where: str,
            field_: str,
            player_stats: frozenset[str] = player_stats,
            check: Callable[[str | None, Context, str, str], None] = check,
        ) -> None:
            for b in bs:
                if b.stat not in player_stats:
                    col.add(
                        "error",
                        "unknown_stat",
                        f"{where}: unknown player stat {b.stat!r}",
                        ctx(),
                        field_,
                    )
                check(b.amount, Context.STAT_BONUS, f"{where} {b.stat}", field_)

        def gear(entries: list[StartingItem], where: str, field_: str) -> None:
            for si in entries:
                if items is not None and si.item not in items:
                    col.add(
                        "warning",
                        "unknown_item",
                        f"{where}: starting item {si.item!r} isn't in this book",
                        ctx(),
                        field_,
                    )

        gear(t.starting_items, f"{p} starting items", f"tiers.{t.key}.starting_items")
        for cls in t.classes:
            for sk in cls.skills:
                if sk not in eff.skills:
                    col.add(
                        "error",
                        "unknown_skill",
                        f"{p} class '{cls.label}' grants unknown skill {sk!r}",
                        ctx(),
                    )
            cf_ = f"tiers.{t.key}.classes.{cls.key}"
            bonuses(cls.modifiers, f"{p} class '{cls.label}'", cf_)
            gear(cls.starting_items, f"{p} class '{cls.label}'", cf_)
        pf = f"tiers.{t.key}.progression"
        pr = t.progression
        check(pr.xp_award, Context.XP_AWARD, f"{p} XP award", pf)
        check(pr.xp_to_next, Context.XP_TO_NEXT, f"{p} XP for next level", pf)
        bonuses(pr.level_up or [], f"{p} level-up bonus", pf)
        mp = eff.progression
        for name, key in (("XP", mp.xp_stat), ("level", mp.level_stat)):
            if key is not None and key not in player_stats:
                col.add(
                    "error",
                    "unknown_stat",
                    f"{p}: the {name} stat {key!r} isn't a player stat",
                    ctx(),
                    pf,
                )
        if (mp.xp_stat or mp.level_stat or mp.xp_award) and not mp.enabled():
            col.add(
                "warning",
                "progression_incomplete",
                f"{p}: levelling needs an XP stat, a level stat and the XP for the next level",
                ctx(),
                pf,
            )
        level_def = eff.stats.get(mp.level_stat or "")
        xp_def = eff.stats.get(mp.xp_stat or "")
        if (
            mp.enabled()
            and t.progression != type(t.progression)()
            and (
                (level_def is not None and level_def.max_is_initial)
                or (xp_def is not None and (xp_def.max_is_initial or xp_def.max is not None))
            )
        ):
            col.add(
                "warning",
                "progression_capped",
                f"{p}: the XP or level stat has a maximum, which can stop levelling up",
                ctx(),
                pf,
            )
        if mp.enabled() and mp.xp_stat == mp.level_stat:
            col.add(
                "error",
                "progression_stats",
                f"{p}: XP and level must be different stats",
                ctx(),
                pf,
            )
        combat = t.combat
        cf = f"tiers.{t.key}.combat"
        check(combat.player_attack, Context.COMBAT_ATTACK, f"{p} player attack", cf)
        check(combat.enemy_attack, Context.COMBAT_ATTACK, f"{p} enemy attack", cf)
        check(combat.damage, Context.COMBAT_ATTACK, f"{p} damage", cf)
        for i, hook in enumerate(combat.damage_hooks):
            check(hook, Context.COMBAT_DAMAGE, f"{p} damage rule {i + 1}", cf)
        # Whole-tier combat sanity uses the merged definition.
        mc = eff.combat
        if mc.damage_stat is not None and mc.damage_stat not in (
            eff.player_stats() & eff.enemy_stats()
        ):
            col.add(
                "error",
                "combat_stat",
                f"{p}: combat damages {mc.damage_stat}, which both sides need",
                ctx(),
            )
        damage_def = eff.stats.get(mc.damage_stat) if mc.damage_stat else None
        if damage_def is not None and damage_def.defeat_at is None:
            col.add(
                "warning",
                "combat_no_defeat",
                f"{p}: {mc.damage_stat} has no defeat value, so fights may never end",
                ctx(),
            )
    return col.problems
