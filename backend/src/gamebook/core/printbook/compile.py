"""The print compiler: a book and a tier in, numbered sections out (SPEC §6.3).

How engine features become pencil-and-dice instructions:

- **Text variants** become a short *router* section ("If you have the Rope, turn to 57.
  Otherwise, turn to 112.") followed by one section per variant. The engine picks the
  variant on arrival, before on-entry effects, and so does the reader.
- **visits()** in any condition gives that node tick boxes ("Tick a box each time you
  arrive"), and conditions read "if you have been to section 23 before".
- **Once-only gains** (and found items) in sections the reader can come back to get a
  tick box too, and read "the first time you are here".
- **Gated choices** read "If you have the Rope, turn to 12"; tier-limited choices are
  left out of lower editions; tests, rolls, fights and tables print the edition's
  numbers.

Every section also carries machine-readable ``links`` and ``routes`` so the verifier
(``verify.py``) can prove the printed book plays like the engine.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from gamebook.core import gbx
from gamebook.core.effects import Effect, effect_to_english, fires_once
from gamebook.core.engine.combat import enemy_stats
from gamebook.core.gbx.scope import RefKind
from gamebook.core.model import BookSnapshot, Choice, Encounter, Node
from gamebook.core.rules.schema import EffectiveTier, effective_tier

ENDINGS = {
    "victory": "Your adventure ends in triumph.",
    "death": "Your adventure ends here.",
    "defeated": "Your adventure ends here.",
    "other": "Your adventure ends here.",
}
MAX_TICKS = 5
#: En dash for number ranges ("1\u20132").
DASH = "\u2013"


# ── keys ─────────────────────────────────────────────────────────────────


def needs_router(node: Node) -> bool:
    return len(node.variants) > 1 or any(v.condition for v in node.variants)


def has_default(node: Node) -> bool:
    return any(not v.condition for v in node.variants)


def reachable_variants(node: Node) -> list[Any]:
    """Variants in the engine's order, up to the first unconditional one (later ones can
    never be chosen, so they get no section)."""
    out = []
    for v in sorted(node.variants, key=lambda v: -v.priority):
        out.append(v)
        if not v.condition:
            break
    return out


def section_keys(book: BookSnapshot) -> list[list[str]]:
    """Section keys per act, in act order (each list in a stable order: by node key)."""
    by_act: dict[str, list[str]] = {a.id: [] for a in sorted(book.acts, key=lambda a: a.position)}
    for n in sorted(book.nodes, key=lambda n: n.key):
        keys = by_act.setdefault(n.act_id, [])
        keys.append(f"n:{n.id}")
        if needs_router(n):
            keys += [f"v:{v.id}" for v in reachable_variants(n)]
            if not has_default(n):
                keys.append(f"p:{n.id}")
    return list(by_act.values())


def pins(book: BookSnapshot) -> dict[str, int]:
    """Author pins, and the start section as 1 unless something else claims 1."""
    out = {f"n:{n.id}": n.section_pin for n in book.nodes if n.section_pin}
    if book.start_node_id and f"n:{book.start_node_id}" not in out and 1 not in out.values():
        out[f"n:{book.start_node_id}"] = 1
    return out


# ── output ───────────────────────────────────────────────────────────────


@dataclass
class Link:
    """A printed "turn to" for one engine move: choice + outcome → section number."""

    choice_id: str
    outcome: str
    number: int | None


@dataclass
class Route:
    variant_id: str | None
    condition: str | None
    number: int


@dataclass
class Block:
    kind: str  # effects | found | shop | choice | ending | note
    data: dict[str, Any]


@dataclass
class Section:
    number: int
    key: str
    node_id: str
    variant_id: str | None
    act_id: str
    #: For proofing only (titles are never printed).
    title: str
    #: router | section
    kind: str
    ticks: int = 0
    tick_note: str = ""
    text: str = ""
    #: The text is the author's beat notes (no approved prose yet).
    draft: bool = False
    blocks: list[Block] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    routes: list[Route] = field(default_factory=list)
    ending: str | None = None


@dataclass
class PrintWarning:
    code: str
    message: str
    node_id: str | None = None
    number: int | None = None


@dataclass
class PrintBook:
    tier: str
    tier_label: str
    sections: list[Section]
    warnings: list[PrintWarning]
    numbers: dict[str, int]
    #: Where the reader begins ("Now turn to section N").
    start: int | None = None

    def by_number(self) -> dict[int, Section]:
        return {s.number: s for s in self.sections}


# ── helpers ──────────────────────────────────────────────────────────────


def _successors(book: BookSnapshot) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {n.id: set() for n in book.nodes}
    for n in book.nodes:
        for c in n.choices:
            for o in c.outcomes:
                if o.target_id:
                    out[n.id].add(o.target_id)
    return out


def revisitable(book: BookSnapshot) -> set[str]:
    """Nodes a reader can arrive at more than once (on a cycle)."""
    succ = _successors(book)
    out = set()
    for start in succ:
        seen: set[str] = set()
        stack = list(succ[start])
        while stack:
            cur = stack.pop()
            if cur == start:
                out.add(start)
                break
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(succ.get(cur, ()))
    return out


def _visit_thresholds(book: BookSnapshot) -> dict[str, int]:
    """Node key → how many tick boxes its visits() conditions need."""
    out: dict[str, int] = {}

    def walk(e: gbx.ast.Expr) -> None:
        match e:
            case gbx.ast.Binary(left=lhs, right=rhs):
                walk(lhs)
                walk(rhs)
            case gbx.ast.Ternary(cond=test, then=then, otherwise=other):
                walk(test)
                walk(then)
                walk(other)
            case gbx.ast.Compare(left=lhs, right=rhs, op=op):
                for call, num, flipped in ((lhs, rhs, False), (rhs, lhs, True)):
                    if (
                        isinstance(call, gbx.ast.Call)
                        and call.func == "visits"
                        and isinstance(num, gbx.ast.Num)
                        and call.args
                        and isinstance(call.args[0], gbx.ast.Name)
                    ):
                        k = int(num.value)
                        o = (
                            {">": "<", "<": ">", ">=": "<=", "<=": ">="}.get(op, op)
                            if flipped
                            else op
                        )
                        need = k + 1 if o in (">", "<=") else k
                        key = call.args[0].name
                        out[key] = min(MAX_TICKS, max(out.get(key, 1), need, 1))
                walk(lhs)
                walk(rhs)
            case gbx.ast.Unary(operand=x):
                walk(x)
            case gbx.ast.Call(func="visits", args=(gbx.ast.Name(name=key),)):
                out.setdefault(key, 1)
            case gbx.ast.Call(args=args):
                for a in args:
                    walk(a)
            case _:
                pass

    sources: list[str] = []
    for n in book.nodes:
        sources += [v.condition for v in n.variants if v.condition]
        sources += [c.condition for c in n.choices if c.condition]
    for src in sources:
        try:
            walk(gbx.parse(src))
        except gbx.GbxSyntaxError:
            continue
    return out


@dataclass
class _Ctx:
    book: BookSnapshot
    tier: EffectiveTier
    tiers: tuple[str, ...]
    numbers: Mapping[str, int]
    prose: Mapping[str, str]
    notes: Mapping[str, str]
    revisit: set[str]
    ticks: dict[str, int]
    warnings: list[PrintWarning]
    node_number: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        keys = {n.key: n.id for n in self.book.nodes}
        self.node_number = {
            key: self.numbers[f"n:{nid}"] for key, nid in keys.items() if f"n:{nid}" in self.numbers
        }
        self._items = {i.key: i.name for i in self.book.items}
        self.items_by_id = {i.id: i for i in self.book.items}

    def in_edition(self, min_tier: str | None) -> bool:
        """Tier-limited content appears in that tier's edition and higher ones."""
        # Same rule as the engine (Game.tier_allows): an unknown tier means never.
        if min_tier is None:
            return True
        if min_tier not in self.tiers:
            return False
        return self.tiers.index(min_tier) <= self.tiers.index(self.tier.key)

    def name(self, kind: RefKind, key: str) -> str:
        t = self.tier
        match kind:
            case RefKind.ITEM:
                return self._items.get(key, key)
            case RefKind.STAT:
                return t.stats[key].label if key in t.stats else key.upper()
            case RefKind.SKILL:
                return t.skills[key].label if key in t.skills else key
            case RefKind.CLASS:
                return t.classes[key].label if key in t.classes else key
            case RefKind.FLAG:
                return key.upper()
            case RefKind.NODE:
                n = self.node_number.get(key)
                return f"section {n}" if n else key
            case RefKind.TIER:
                return key
        return key

    def cond(self, src: str | None) -> str:
        if not src:
            return ""
        try:
            return gbx.condition_to_english(gbx.parse(src), self.name, tiers=self.tiers)
        except Exception:  # unusual expression: say what we can, and warn
            self.warnings.append(PrintWarning("unprintable_condition", f"Couldn't phrase {src!r}"))
            return src

    def num(self, src: str | None) -> str:
        if not src:
            return ""
        try:
            return gbx.number_to_english(gbx.parse(src), self.name, tiers=self.tiers)
        except Exception:
            return src

    def effects(self, effects: Sequence[Effect]) -> list[str]:
        """Effects this edition applies, in English (tier-limited ones are left out)."""
        return [effect_to_english(e, self.name) for e in effects if self.in_edition(e.min_tier)]


# ── compile ──────────────────────────────────────────────────────────────


def compile_book(
    book: BookSnapshot,
    tier: str,
    numbers: Mapping[str, int],
    *,
    prose: Mapping[str, str],
    notes: Mapping[str, str],
) -> PrintBook:
    """Compile a book for one tier's edition. ``prose`` is approved text per variant id;
    ``notes`` are beat notes per node id (printed, marked as draft, where prose is missing)."""
    assert book.rules is not None, "the series has no rule system"
    t = effective_tier(book.rules, tier)
    ctx = _Ctx(
        book,
        t,
        book.rules.tier_keys(),
        numbers,
        prose,
        notes,
        revisitable(book),
        _visit_thresholds(book),
        [],
    )
    sections: list[Section] = []
    for n in book.nodes:
        sections += _node_sections(ctx, n)
    sections.sort(key=lambda s: s.number)
    start = numbers.get(f"n:{book.start_node_id}") if book.start_node_id else None
    if start not in (None, 1):
        ctx.warnings.append(
            PrintWarning(
                "start_not_one",
                f"The book starts at section {start}, not 1 (another section is pinned to 1, "
                "or the start isn't in the first act)",
                book.start_node_id,
                start,
            )
        )
    return PrintBook(t.key, t.label, sections, ctx.warnings, dict(numbers), start)


def _node_sections(c: _Ctx, n: Node) -> list[Section]:
    entry = c.numbers[f"n:{n.id}"]
    ticks = c.ticks.get(n.key, 0)
    once_here = n.id in c.revisit and (any(fires_once(e) for e in n.on_enter) or bool(n.items))
    if once_here:
        ticks = max(ticks, 1)
    tick_note = ""
    if ticks:
        tick_note = (
            "Tick a box each time you arrive here."
            if ticks > 1 or n.key in c.ticks
            else "When you arrive, tick the box if it is empty."
        )
    if not needs_router(n):
        v = n.variants[0] if n.variants else None
        s = _section(c, n, v, entry, f"n:{n.id}", once_here)
        s.ticks, s.tick_note = ticks, tick_note
        return [s]
    router = Section(entry, f"n:{n.id}", n.id, None, n.act_id, n.title, "router")
    router.ticks, router.tick_note = ticks, tick_note
    out = [router]
    for v in reachable_variants(n):
        num = c.numbers[f"v:{v.id}"]
        router.routes.append(Route(v.id, v.condition, num))
        out.append(_section(c, n, v, num, f"v:{v.id}", once_here))
        if not v.condition:
            break  # later variants can never be chosen
    if not has_default(n):
        num = c.numbers[f"p:{n.id}"]
        router.routes.append(Route(None, None, num))
        out.append(_section(c, n, None, num, f"p:{n.id}", once_here))
    lines = []
    for i, r in enumerate(router.routes):
        if r.condition:
            lines.append({"text": f"If {c.cond(r.condition)}, turn to", "n": r.number})
        else:
            lines.append({"text": "Otherwise, turn to" if i else "Turn to", "n": r.number})
    router.blocks.append(Block("route", {"lines": lines}))
    return out


def first_visit_lead(s: Section, entry: int) -> str:
    where = "" if s.number == entry else f" at section {entry}"
    return f"If this is your first visit (the first box{where} was empty when you arrived):"


def _section(c: _Ctx, n: Node, v: Any, number: int, key: str, once_here: bool) -> Section:
    entry = c.numbers[f"n:{n.id}"]
    s = Section(number, key, n.id, v.id if v else None, n.act_id, n.title, "section")
    text = c.prose.get(v.id, "") if v else ""
    if text.strip():
        s.text = text
    else:
        s.text = c.notes.get(n.id, "").strip()
        s.draft = True
        c.warnings.append(
            PrintWarning(
                "no_prose",
                f"{n.title}{f' ({v.label})' if v and v.label != 'Default' else ''} has no "
                "approved prose; its beat notes are printed instead",
                n.id,
                number,
            )
        )
    if n.on_enter:
        lines: list[str] = []
        firsts: list[str] = []
        for e in n.on_enter:
            if not c.in_edition(e.min_tier):
                continue
            (firsts if once_here and fires_once(e) else lines).append(effect_to_english(e, c.name))
        if firsts:
            s.blocks.append(
                Block(
                    "effects",
                    {"lead": first_visit_lead(s, entry), "lines": firsts},
                )
            )
        if lines:
            s.blocks.append(Block("effects", {"lead": "", "lines": lines}))
    if n.ending_kind:
        s.ending = n.ending_kind
        s.blocks.append(
            Block(
                "ending",
                {"kind": n.ending_kind, "text": ENDINGS.get(n.ending_kind, ENDINGS["other"])},
            )
        )
        return s
    if n.items:
        found = []
        for p in n.items:
            item = c.items_by_id.get(p.item_id)
            if item:
                found.append({"name": item.name, "qty": p.qty, "box": once_here})
        if found:
            s.blocks.append(Block("found", {"items": found}))
    if n.shop is not None:
        rows = []
        for offer in n.shop:
            item = c.items_by_id.get(offer.item_id)
            if item:
                rows.append({"name": item.name, "price": offer.price, "stock": offer.stock})
        currency = next((st.label for st in c.tier.stats.values() if st.kind == "resource"), "gold")
        s.blocks.append(
            Block("shop", {"rows": rows, "currency": currency, "sell_rate": n.shop_sell_rate})
        )
    for ch in n.choices:
        if not c.in_edition(ch.min_tier):
            continue
        s.blocks.append(_choice(c, n, ch, s))
    if not any(b.kind == "choice" for b in s.blocks):
        c.warnings.append(
            PrintWarning(
                "dead_end", f"{n.title} has no choices or ending in this edition", n.id, number
            )
        )
    return s


def _target(c: _Ctx, n: Node, ch: Choice, key: str, s: Section) -> int | None:
    out = next((o for o in ch.outcomes if o.key == key), None)
    number = c.numbers.get(f"n:{out.target_id}") if out and out.target_id else None
    if out is not None:
        s.links.append(Link(ch.id, key, number))
        if number is None:
            c.warnings.append(
                PrintWarning(
                    "no_target",
                    f"{n.title}: '{ch.label}' ({key}) leads nowhere",
                    n.id,
                    s.number,
                )
            )
    return number


def _choice(c: _Ctx, n: Node, ch: Choice, s: Section) -> Block:
    data: dict[str, Any] = {
        "label": ch.label,
        "condition": c.cond(ch.condition),
        "choice_id": ch.id,
        "kind": ch.kind,
        "outcomes": [],
    }
    # On a revisitable section, once-only effects are ticked off; the rest repeat.
    split = n.id in c.revisit
    data["effects"] = c.effects([e for e in ch.effects if not (split and fires_once(e))])
    data["first_effects"] = c.effects([e for e in ch.effects if split and fires_once(e)])
    match ch.kind:
        case "goto":
            data["outcomes"].append({"text": "turn to", "n": _target(c, n, ch, "default", s)})
        case "roll":
            data["dice"] = c.num(ch.dice or "2d6")
            for o in ch.outcomes:
                if o.range_lo is None or o.range_hi is None:
                    continue
                span = (
                    str(o.range_lo)
                    if o.range_lo == o.range_hi
                    else f"{o.range_lo}{DASH}{o.range_hi}"
                )
                data["outcomes"].append(
                    {"text": f"{span}: turn to", "n": _target(c, n, ch, o.key, s)}
                )
        case "test":
            test = c.tier.tests.get(ch.test or "")
            if test is None:
                c.warnings.append(
                    PrintWarning(
                        "no_test",
                        f"{n.title}: the test {ch.test!r} isn't in this tier",
                        n.id,
                        s.number,
                    )
                )
                data["test"] = {"label": ch.test or "?", "roll": "", "success": "", "after": []}
            else:
                data["test"] = {
                    "label": test.label,
                    "roll": c.num(test.roll),
                    "success": c.cond(test.success),
                    "after": c.effects(test.after),
                }
            data["outcomes"] += [
                {"text": "If you succeed, turn to", "n": _target(c, n, ch, "success", s)},
                {"text": "If you fail, turn to", "n": _target(c, n, ch, "failure", s)},
            ]
        case "combat":
            enc = next((e for e in n.encounters if e.id == ch.encounter_id), None)
            data["fight"] = _fight(c, enc) if enc else None
            win = _target(c, n, ch, "win", s)
            data["outcomes"].append({"text": "If you win, turn to", "n": win})
            lose_out = next((o for o in ch.outcomes if o.key == "lose"), None)
            if lose_out and lose_out.target_id:
                data["outcomes"].append(
                    {"text": "If you lose, turn to", "n": _target(c, n, ch, "lose", s)}
                )
            else:
                data["outcomes"].append(
                    {"text": "If you lose, your adventure ends here.", "n": None}
                )
            if ch.flee_allowed and c.tier.combat.flee_allowed:
                cost = c.effects(c.tier.combat.flee_cost or [])
                data["outcomes"].append(
                    {
                        "text": "You may flee"
                        + (f" ({' '.join(cost).rstrip('.')})" if cost else "")
                        + ": turn to",
                        "n": _target(c, n, ch, "flee", s),
                    }
                )
    return Block("choice", data)


def _fight(c: _Ctx, enc: Encounter) -> dict[str, Any]:
    keys = [k for k, st in c.tier.stats.items() if "enemy" in st.applies_to]
    labels = [c.tier.stats[k].label for k in keys]
    enemies = {e.id: e for e in c.book.enemies}
    by_key = {e.key: e for e in c.book.enemies}

    # Readers work out XP from the enemy's level, so print it when fights give XP.
    pr = c.tier.progression
    show_level = pr.enabled() and bool(pr.xp_award)

    def row(enemy: Any, level: int, count: int) -> dict[str, Any]:
        stats = enemy_stats(enemy.stat_formulas, level, frozenset(keys), c.tiers, c.tier.key)
        return {
            "name": enemy.name,
            "count": count,
            "stats": [stats.get(k, 0) for k in keys],
            "level": level if show_level else None,
        }

    out: dict[str, Any] = {
        "labels": labels,
        "together": enc.fight == "simultaneous",
        "enemies": [],
        "table": None,
    }
    if enc.mode == "fixed":
        out["enemies"] = [
            row(enemies[ee.enemy_id], ee.level, ee.count)
            for ee in enc.enemies
            if ee.enemy_id in enemies
        ]
        return out
    table = next((t for t in c.book.tables if t.id == enc.table_id), None)
    if table is None:
        return out
    rows = []
    for e in table.entries:
        span = str(e.lo) if e.lo == e.hi else f"{e.lo}{DASH}{e.hi}"
        if e.kind == "enemies":
            foes = [row(by_key[k], lvl, cnt) for k, lvl, cnt in e.enemies if k in by_key]
            if foes:
                rows.append({"span": span, "kind": "enemies", "enemies": foes})
            else:  # the engine finds nobody to fight: a win
                rows.append({"span": span, "kind": "nothing", "text": "Nothing happens"})
        elif e.kind == "item":
            rows.append(
                {
                    "span": span,
                    "kind": "item",
                    "text": f"You find {c.name(RefKind.ITEM, e.item or '')}"
                    + (f" x{e.qty}" if e.qty > 1 else ""),
                }
            )
        elif e.kind == "gold":
            rows.append(
                {"span": span, "kind": "gold", "text": f"You find {c.num(e.amount or '0')} gold"}
            )
        else:
            rows.append({"span": span, "kind": "nothing", "text": "Nothing happens"})
    out["table"] = {"name": table.name, "dice": c.num(table.dice), "rows": rows}
    return out


def first_numbers(book: PrintBook) -> dict[str, int]:
    """Act id → its lowest section number (where its opener goes)."""
    out: dict[str, int] = {}
    for s in book.sections:
        out[s.act_id] = min(out.get(s.act_id, s.number), s.number)
    return out


__all__ = [
    "Block",
    "Link",
    "PrintBook",
    "Route",
    "Section",
    "compile_book",
    "first_numbers",
    "needs_router",
    "pins",
    "section_keys",
]
