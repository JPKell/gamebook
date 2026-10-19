"""State digest: what a reader must / may have when they arrive at each node.

A forward dataflow analysis over the book graph for one tier (SPEC §2.9). Facts
are codewords (flags), items held, characters met and skills known:

* **must**: true on *every* path to the node (intersection over incoming paths);
* **may**: true on *some* path (union).

The state at a node is the state after its on-entry effects (what the prose can
assume). Along a choice, the analysis adds what the reader *might* do first
(optional pickups, purchases, using consumables, selling), what the choice's
condition guarantees (passing ``has(rope)`` means you have rope), the choice's
effects, and a test's after-effects. Loops are handled by iterating to a
fixpoint; the lattice is finite, so it terminates.

Deliberately approximate: item *counts* and stat values are not tracked, and
``visits()``/stat comparisons are "unknown". The analysis is sound for what it
reports as must (barring stat-gated effects) and is used for gate verdicts:
a condition that is false for every reader is "never satisfiable".
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from gamebook.core import gbx
from gamebook.core.effects import (
    ChooseClass,
    ClearFlag,
    Effect,
    GiveItem,
    LearnSkill,
    SetFlag,
    TakeItem,
    fires_once,
)
from gamebook.core.gbx.ast import Binary, Bool, Call, Compare, Expr, Name, Num, Unary
from gamebook.core.model import BookSnapshot, Choice, Node
from gamebook.core.rules.schema import EffectiveTier, effective_tier

FactKind = Literal["flag", "item", "character", "skill"]
Fact = tuple[FactKind, str]
Facts = frozenset[Fact]

#: Three-valued truth: True, False, or None (unknown / depends on the path).
Verdict = bool | None


@dataclass(frozen=True)
class State:
    must: Facts
    may: Facts

    def add(self, facts: Iterable[Fact]) -> State:
        f = frozenset(facts)
        return State(self.must | f, self.may | f)

    def maybe(self, facts: Iterable[Fact]) -> State:
        return State(self.must, self.may | frozenset(facts))

    def lose(self, facts: Iterable[Fact], *, surely: bool) -> State:
        """Facts that may (``surely=False``) or definitely go away."""
        f = frozenset(facts)
        return State(self.must - f, self.may - f if surely else self.may)


def _join(a: State | None, b: State) -> State:
    if a is None:
        return b
    return State(a.must & b.must, a.may | b.may)


@dataclass
class NodeDigest:
    reachable: bool = False
    #: Fewest choices from the start (None if unreachable).
    depth_min: int | None = None
    #: Most choices from the start; None when a loop makes it unbounded (or unreachable).
    depth_max: int | None = None
    state: State | None = None
    #: The predecessor on a shortest path from the start (first by choice order).
    canonical_predecessor: str | None = None
    #: Choice id → whether its condition holds for every reader / no reader / depends.
    gates: dict[str, Verdict] = field(default_factory=dict)

    def facts(self, kind: FactKind, which: Literal["must", "may"]) -> list[str]:
        if self.state is None:
            return []
        if which == "must":
            return sorted(k for t, k in self.state.must if t == kind)
        return sorted(k for t, k in self.state.may - self.state.must if t == kind)


@dataclass
class Digest:
    tier: str
    nodes: dict[str, NodeDigest]


# ── effects ──────────────────────────────────────────────────────────────


def _gain(e: Effect) -> Fact | None:
    match e:
        case SetFlag(flag=f):
            return ("flag", f)
        case GiveItem(item=k, qty=q) if q > 0:
            return ("item", k)
        case LearnSkill(skill=s):
            return ("skill", s)
    return None


def _loss(e: Effect) -> Fact | None:
    match e:
        case ClearFlag(flag=f):
            return ("flag", f)
        case TakeItem(item=k):
            return ("item", k)
    return None


def _apply(
    state: State,
    effects: Sequence[Effect],
    tier: _TierCtx,
    *,
    repeatable: bool = False,
    removable: Facts = frozenset(),
) -> State:
    """Apply effects in order.

    A once-only gain on a source the reader can come back to (``repeatable``) is
    only "may" when something can remove the fact in between: on the second
    visit it doesn't fire again, so it isn't guaranteed any more.
    """
    for e in effects:
        if not tier.allows(e.min_tier):
            continue
        if isinstance(e, ChooseClass):
            state = _choose_class(state, e, tier)
            continue
        gain, loss = _gain(e), _loss(e)
        if gain is not None:
            if repeatable and gain in removable and fires_once(e):
                state = state.maybe([gain])
            else:
                state = state.add([gain])
        elif loss is not None:
            # Taking one item may leave others; clearing a flag always removes it.
            state = state.lose([loss], surely=loss[0] == "flag")
    return state


def _class_skills(eff: EffectiveTier, keys: Iterable[str]) -> list[Facts]:
    return [frozenset(("skill", s) for s in eff.classes[k].skills) for k in keys]


def _choose_class(state: State, e: ChooseClass, tier: _TierCtx) -> State:
    """The offered classes' skills become possible (not certain: a reader who already
    has a class picks nothing)."""
    eff = tier.eff
    if eff is None or eff.class_choice != "story":
        return state
    sets = _class_skills(eff, [k for k in eff.classes if not e.classes or k in e.classes])
    if not sets:
        return state
    return state.maybe(frozenset.union(*sets))


# ── conditions (three-valued) ────────────────────────────────────────────


def _arg(call: Call) -> str | None:
    return call.args[0].name if len(call.args) == 1 and isinstance(call.args[0], Name) else None


_FACT_FUNCS: dict[str, FactKind] = {"has": "item", "flag": "flag", "skill": "skill"}


def judge(expr: Expr, state: State) -> Verdict:
    """Does ``expr`` hold for every reader in ``state`` (True), none (False), or some (None)?"""
    match expr:
        case Bool(value=v):
            return v
        case Call(func=func) if func in _FACT_FUNCS and _arg(expr):
            fact: Fact = (_FACT_FUNCS[func], _arg(expr) or "")
            if fact in state.must:
                return True
            if fact not in state.may:
                return False
            return None
        case Call(func="equipped") if _arg(expr):
            return False if ("item", _arg(expr) or "") not in state.may else None
        case Compare(op=op, left=Call(func="count") as c, right=Num(value=n)) if _arg(c):
            needs_one = (op == ">=" and n >= 1) or (op == ">" and n >= 0) or (op == "==" and n >= 1)
            if needs_one and ("item", _arg(c) or "") not in state.may:
                return False
            return None
        case Unary(op="not", operand=inner):
            verdict = judge(inner, state)
            return None if verdict is None else not verdict
        case Binary(op="and", left=a, right=b):
            va, vb = judge(a, state), judge(b, state)
            if va is False or vb is False:
                return False
            return True if va is True and vb is True else None
        case Binary(op="or", left=a, right=b):
            va, vb = judge(a, state), judge(b, state)
            if va is True or vb is True:
                return True
            return False if va is False and vb is False else None
    return None


def _guarantees(expr: Expr) -> tuple[set[Fact], set[Fact]]:
    """Facts a passed condition proves present / absent (top-level conjunction only)."""
    present: set[Fact] = set()
    absent: set[Fact] = set()
    match expr:
        case Binary(op="and", left=a, right=b):
            for part in (a, b):
                p, q = _guarantees(part)
                present |= p
                absent |= q
        case Call(func=func) if func in _FACT_FUNCS and _arg(expr):
            present.add((_FACT_FUNCS[func], _arg(expr) or ""))
        case Unary(op="not", operand=Call(func=func) as inner) if func in _FACT_FUNCS and _arg(
            inner
        ):
            absent.add((_FACT_FUNCS[func], _arg(inner) or ""))
    return present, absent


def _parse(src: str | None) -> Expr | None:
    if not src:
        return None
    try:
        return gbx.parse(src)
    except gbx.GbxSyntaxError:
        return None


# ── the analysis ─────────────────────────────────────────────────────────


@dataclass
class _TierCtx:
    keys: tuple[str, ...]
    tier: str
    eff: EffectiveTier | None

    def allows(self, min_tier: str | None) -> bool:
        if min_tier is None:
            return True
        if min_tier not in self.keys:
            return False
        return self.keys.index(min_tier) <= self.keys.index(self.tier)


def _choices(node: Node, tier: _TierCtx) -> list[Choice]:
    return [c for c in node.choices if tier.allows(c.min_tier)]


class _Book:
    """Per-book lookups the transfer functions need."""

    def __init__(self, book: BookSnapshot, tier: _TierCtx) -> None:
        self.book = book
        self.tier = tier
        self.nodes = {n.id: n for n in book.nodes}
        available = [i for i in book.items if book.available(i)]
        self.item_key = {i.id: i.key for i in available}
        # Consumable item fact -> (facts its use may give, facts it may remove).
        self.consumables: dict[Fact, tuple[Facts, Facts]] = {}
        for i in available:
            if i.category == "consumable" and i.use_effects:
                effs = [e for e in i.use_effects if tier.allows(e.min_tier)]
                self.consumables[("item", i.key)] = (
                    frozenset(g for e in effs if (g := _gain(e)) is not None),
                    frozenset(x for e in effs if (x := _loss(e)) is not None),
                )
        self.sellable: Facts = frozenset(
            ("item", i.key) for i in available if i.value > 0 and i.category != "key"
        )
        self.character_key = {c.id: c.key for c in book.characters}
        self.tables = {t.id: t for t in book.tables if book.available(t)}
        self.conditions: dict[str, Expr | None] = {}
        self.flee_cost: Sequence[Effect] = (tier.eff.combat.flee_cost or []) if tier.eff else []

        # Every effect in the book, for "can this fact go away?" and "set elsewhere?".
        effects: list[Effect] = []
        for n in book.nodes:
            effects += n.on_enter
            for c in n.choices:
                effects += c.effects
        for i in available:
            effects += i.use_effects
        if tier.eff is not None:
            for t in tier.eff.tests.values():
                effects += t.after
        effects += self.flee_cost
        self.removable: Facts = frozenset(
            x for e in effects if (x := _loss(e)) is not None
        ) | frozenset(self.consumables)
        if any(n.shop_sell_rate for n in book.nodes):
            self.removable |= self.sellable
        self.flags_set_here = frozenset(e.flag for e in effects if isinstance(e, SetFlag))
        #: Nodes a reader can arrive at more than once (in a loop); set by compute().
        self.cyclic: frozenset[str] = frozenset()

    def condition(self, c: Choice) -> Expr | None:
        if c.id not in self.conditions:
            self.conditions[c.id] = _parse(c.condition)
        return self.conditions[c.id]

    def arrive(self, node: Node, state: State) -> State:
        state = _apply(
            state,
            node.on_enter,
            self.tier,
            repeatable=node.id in self.cyclic,
            removable=self.removable,
        )
        met: list[Fact] = [
            ("character", self.character_key[c])
            for c in node.character_ids
            if c in self.character_key
        ]
        return state.add(met)

    def before_choosing(self, node: Node, state: State) -> State:
        """What the reader might do at a node before picking a choice."""
        found: list[Fact] = [
            ("item", self.item_key[p.item_id]) for p in node.items if p.item_id in self.item_key
        ]
        state = state.maybe(found)
        if node.shop is not None:
            bought: list[Fact] = [
                ("item", self.item_key[e.item_id]) for e in node.shop if e.item_id in self.item_key
            ]
            state = state.maybe(bought)
            if node.shop_sell_rate:
                state = state.lose(self.sellable & state.must, surely=False)
        return self.use_consumables(state)

    def use_consumables(self, state: State) -> State:
        """The reader may have used any consumable they may hold (until nothing changes)."""
        must, may = set(state.must), set(state.may)
        while True:
            grew = False
            for item, (gains, losses) in self.consumables.items():
                if item in may:
                    must.discard(item)
                    must.difference_update(losses)
                    if not gains <= may:
                        may |= gains
                        grew = True
            if not grew:
                return State(frozenset(must), frozenset(may))

    def along(self, node: Node, c: Choice, key: str, state: State) -> State:
        cond = self.condition(c)
        if cond is not None:
            present, absent = _guarantees(cond)
            state = State(state.must | present, state.may | present)
            state = state.lose(absent, surely=True)
        state = _apply(
            state,
            c.effects,
            self.tier,
            repeatable=node.id in self.cyclic,
            removable=self.removable,
        )
        if c.kind == "test" and self.tier.eff is not None:
            test = self.tier.eff.tests.get(c.test or "")
            if test is not None:
                state = _apply(state, test.after, self.tier)
        if c.kind == "combat":
            enc = next((e for e in node.encounters if e.id == c.encounter_id), None)
            table = self.tables.get(enc.table_id or "") if enc and enc.mode == "table" else None
            if table is not None:
                drops: list[Fact] = [
                    ("item", e.item) for e in table.entries if e.kind == "item" and e.item
                ]
                state = state.maybe(drops)
            if key == "flee":
                state = _apply(state, self.flee_cost, self.tier)
            state = self.use_consumables(state)  # potions drunk mid-fight
        return state


def _initial(b: _Book) -> State:
    """Class skills, plus codewords only other books set (a reader may bring them along)."""
    from_elsewhere: Facts = frozenset(
        ("flag", f) for f in b.book.series_flags_set - b.flags_set_here
    )
    eff = b.tier.eff
    if eff is None or not eff.classes or eff.class_choice != "start":
        return State(frozenset(), from_elsewhere)
    sets = _class_skills(eff, eff.classes)
    return State(frozenset.intersection(*sets), frozenset.union(*sets) | from_elsewhere)


def compute(book: BookSnapshot, tier: str | None = None) -> Digest:
    """The digest for one tier (default: the highest, where every choice is available)."""
    keys = book.rules.tier_keys() if book.rules else ()
    tier_key = tier if tier in keys else (keys[-1] if keys else "")
    eff = effective_tier(book.rules, tier_key) if book.rules and tier_key else None
    tctx = _TierCtx(tuple(keys), tier_key, eff)
    b = _Book(book, tctx)
    out = {n.id: NodeDigest() for n in book.nodes}
    start = book.start_node_id
    if start is None or start not in b.nodes:
        return Digest(tier_key, out)

    edges: dict[str, list[tuple[Choice, str, str]]] = {
        n.id: [
            (c, o.key, o.target_id)
            for c in _choices(n, tctx)
            for o in c.outcomes
            if o.target_id is not None and o.target_id in b.nodes
        ]
        for n in book.nodes
    }
    adj = {n: sorted({t for _c, _k, t in es}) for n, es in edges.items()}
    b.cyclic = frozenset(
        n for comp in _sccs(adj, start) for n in comp if len(comp) > 1 or comp[0] in adj[comp[0]]
    )

    # Fixpoint of arrival states. Choices nobody can take are skipped, so they
    # neither "prove" their condition's facts nor make anything reachable.
    arrive: dict[str, State | None] = dict.fromkeys(b.nodes)
    arrive[start] = b.arrive(b.nodes[start], _initial(b))
    work = deque([start])
    queued = {start}
    while work:
        cur = work.popleft()
        queued.discard(cur)
        here = arrive[cur]
        assert here is not None
        node = b.nodes[cur]
        if node.ending_kind is not None:
            continue
        base = b.before_choosing(node, here)
        for c, key, t in edges[cur]:
            cond = b.condition(c)
            if cond is not None and judge(cond, base) is False:
                continue
            incoming = b.arrive(b.nodes[t], b.along(node, c, key, base))
            joined = _join(arrive[t], incoming)
            if joined != arrive[t]:
                arrive[t] = joined
                if t not in queued:
                    queued.add(t)
                    work.append(t)

    # Depths and canonical predecessor over the choices someone can actually take.
    live: dict[str, list[str]] = {n: [] for n in b.nodes}
    for nid, here in arrive.items():
        node = b.nodes[nid]
        if here is None or node.ending_kind is not None:
            continue
        base = b.before_choosing(node, here)
        for c, _key, t in edges[nid]:
            cond = b.condition(c)
            if (cond is None or judge(cond, base) is not False) and t not in live[nid]:
                live[nid].append(t)
    out[start].reachable, out[start].depth_min = True, 0
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for t in live[cur]:
            if not out[t].reachable:
                out[t].reachable = True
                out[t].depth_min = (out[cur].depth_min or 0) + 1
                out[t].canonical_predecessor = cur
                queue.append(t)
    _max_depths(out, live, start)

    for nid, d in out.items():
        d.state = arrive[nid]
        if d.state is None:
            continue
        node = b.nodes[nid]
        base = b.before_choosing(node, d.state)
        for c in _choices(node, tctx):
            cond = b.condition(c)
            if cond is not None:
                d.gates[c.id] = judge(cond, base)
    return Digest(tier_key, out)


def _max_depths(out: dict[str, NodeDigest], live: dict[str, list[str]], start: str) -> None:
    """Longest path from the start; unbounded (None) through or after any loop."""
    adj = {n: sorted(set(ts)) for n, ts in live.items()}
    sccs = _sccs(adj, start)
    comp = {n: i for i, members in enumerate(sccs) for n in members}
    cyclic = {
        i for i, members in enumerate(sccs) if len(members) > 1 or members[0] in adj[members[0]]
    }
    preds: dict[int, set[int]] = {i: set() for i in range(len(sccs))}
    for n, targets in adj.items():
        if n not in comp:
            continue
        for t in targets:
            if comp[t] != comp[n]:
                preds[comp[t]].add(comp[n])
    # Tarjan yields SCCs in reverse topological order, so walk them backwards.
    best: dict[int, int | None] = {}
    for i in reversed(range(len(sccs))):
        if start in sccs[i]:
            value: int | None = None if i in cyclic else 0
        elif i in cyclic or any(best.get(p) is None for p in preds[i]) or not preds[i]:
            value = None
        else:
            value = max((best[p] or 0) + 1 for p in preds[i])
        best[i] = value
    for i, members in enumerate(sccs):
        for n in members:
            out[n].depth_max = best.get(i)


def _sccs(adj: dict[str, list[str]], root: str) -> list[list[str]]:
    """Tarjan's SCCs of the part reachable from ``root`` (iterative)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    result: list[list[str]] = []
    counter = 0
    work: list[tuple[str, int]] = [(root, 0)]
    while work:
        v, i = work.pop()
        if i == 0:
            index[v] = low[v] = counter
            counter += 1
            stack.append(v)
            on_stack.add(v)
        recurse = False
        for j in range(i, len(adj[v])):
            w = adj[v][j]
            if w not in index:
                work.append((v, j + 1))
                work.append((w, 0))
                recurse = True
                break
            if w in on_stack:
                low[v] = min(low[v], index[w])
        if recurse:
            continue
        if low[v] == index[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            result.append(comp)
        if work:
            parent = work[-1][0]
            low[parent] = min(low[parent], low[v])
    return result
