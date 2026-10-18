"""Context assembly for prose pipelines (SPEC §5.1), with token budgeting.

``BookData`` loads everything a book's contexts need once (nodes, outline, lore,
characters, prose, digest), so a whole act or the writing queue costs a handful
of queries. ``assemble`` builds one variant's context as plain data for the
templates, trims it to a token budget, and hashes the inputs that decide
whether approved prose is stale.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from gamebook.core.analysis.digest import Digest, FactKind
from gamebook.core.analysis.digest import compute as compute_digest
from gamebook.core.model import BookSnapshot
from gamebook.db.models import (
    Act,
    Book,
    Character,
    Choice,
    Encounter,
    Enemy,
    Item,
    LoreEntry,
    Node,
    ProseVersion,
    Series,
    StoryBeat,
)
from gamebook.llm.client import estimate_tokens
from gamebook.services import refs, snapshot
from gamebook.services.common import require

DEFAULT_STYLE: dict[str, Any] = {
    "pov": "second",
    "tense": "present",
    "word_min": 150,
    "word_max": 400,
    "voice": "",
    "notes": "",
}
#: How many approved summaries back along the canonical path go into "story so far".
STORY_HOPS = 8
#: Lore and character text longer than this is cut (characters, not tokens).
LORE_CHARS = 1200

_FACT_WORDS: dict[FactKind, str] = {
    "flag": "codewords",
    "item": "items",
    "character": "has met",
    "skill": "skills",
}


def _style(*layers: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(DEFAULT_STYLE)
    for layer in layers:
        out.update({k: v for k, v in (layer or {}).items() if v not in (None, "")})
    return out


def _clip(text: str, limit: int = LORE_CHARS) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


@dataclass
class BookData:
    book: Book
    series: Series
    nodes: dict[str, Node]
    acts: dict[str, Act]
    beats_by_node: dict[str, list[StoryBeat]]
    characters: dict[str, Character]
    lore: dict[str, LoreEntry]
    item_names: dict[str, str]
    enemy_names: dict[str, str]
    #: variant id → its versions, newest first
    prose: dict[str, list[ProseVersion]]
    digest: Digest
    labels: dict[FactKind, dict[str, str]] = field(default_factory=dict)
    _variants: dict[str, tuple[Node, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, session: Session, book_id: str, snap: BookSnapshot | None = None) -> BookData:
        book = require(session, Book, book_id)
        series = require(session, Series, book.series_id)
        nodes = {
            n.id: n
            for n in session.scalars(
                select(Node)
                .where(Node.book_id == book_id)
                .options(
                    selectinload(Node.variants),
                    selectinload(Node.choices).selectinload(Choice.outcomes),
                    selectinload(Node.encounters).selectinload(Encounter.enemies),
                    selectinload(Node.items),
                    selectinload(Node.shop_items),
                    selectinload(Node.characters),
                )
            )
        }
        acts = {
            a.id: a
            for a in session.scalars(
                select(Act)
                .where(Act.book_id == book_id)
                .options(selectinload(Act.beats).selectinload(StoryBeat.links))
            )
        }
        beats_by_node: dict[str, list[StoryBeat]] = {}
        for a in sorted(acts.values(), key=lambda a: a.position):
            for b in a.beats:
                for nid in b.node_ids:
                    beats_by_node.setdefault(nid, []).append(b)

        def scoped(model: type[Any]) -> list[Any]:
            return list(
                session.scalars(
                    select(model).where(
                        model.series_id == series.id,
                        (model.book_id.is_(None)) | (model.book_id == book_id),
                    )
                )
            )

        prose: dict[str, list[ProseVersion]] = {}
        for pv in session.scalars(
            select(ProseVersion)
            .where(ProseVersion.book_id == book_id)
            .order_by(ProseVersion.created_at.desc())
        ):
            prose.setdefault(pv.variant_id, []).append(pv)
        snap = snap or snapshot.book_snapshot(session, book_id)
        digest = compute_digest(snap)
        characters = {c.id: c for c in scoped(Character)}
        items = scoped(Item)
        labels: dict[FactKind, dict[str, str]] = {
            "flag": {},
            "item": {i.key: i.name for i in items},
            "character": {c.key: c.name for c in characters.values()},
            "skill": {},
        }
        if snap.rules:
            for t in snap.rules.tiers:
                for sk in t.skills:
                    labels["skill"][sk.key] = sk.label
        return cls(
            book=book,
            series=series,
            nodes=nodes,
            acts=acts,
            beats_by_node=beats_by_node,
            characters=characters,
            lore={x.id: x for x in scoped(LoreEntry)},
            item_names={i.id: i.name for i in items},
            enemy_names={e.id: e.name for e in scoped(Enemy)},
            prose=prose,
            digest=digest,
            labels=labels,
        )

    def variant(self, variant_id: str) -> tuple[Node, Any]:
        if not self._variants:
            self._variants = {v.id: (n, v) for n in self.nodes.values() for v in n.variants}
        return self._variants[variant_id]

    # ── prose lookups ──

    def approved(self, variant_id: str) -> ProseVersion | None:
        return next((p for p in self.prose.get(variant_id, []) if p.status == "approved"), None)

    def latest(self, variant_id: str) -> ProseVersion | None:
        versions = self.prose.get(variant_id, [])
        return versions[0] if versions else None

    def node_text(self, node: Node) -> tuple[str, bool] | None:
        """A node's best text for continuity: (text, approved?) — approved first,
        else the newest draft / in-review version of its first variant that has one."""
        for v in node.variants:
            pv = self.approved(v.id)
            if pv is not None:
                return pv.text, True
        for v in node.variants:
            pv = next(
                (p for p in self.prose.get(v.id, []) if p.status in ("in_review", "draft")), None
            )
            if pv is not None:
                return pv.text, False
        return None

    def node_summary(self, node: Node) -> str | None:
        for v in node.variants:
            pv = self.approved(v.id)
            if pv is not None and pv.summary:
                return pv.summary
        return None

    def predecessor(self, node: Node) -> Node | None:
        nd = self.digest.nodes.get(node.id)
        pid = node.canonical_predecessor_id or (nd.canonical_predecessor if nd else None)
        return self.nodes.get(pid or "")

    def facts_text(self, node_id: str, which: str) -> str:
        nd = self.digest.nodes.get(node_id)
        if nd is None or nd.state is None:
            return ""
        parts = []
        for kind, word in _FACT_WORDS.items():
            keys = nd.facts(kind, "must" if which == "must" else "may")
            if keys:
                names = [self.labels.get(kind, {}).get(k, k) for k in keys]
                parts.append(f"{word}: {', '.join(names)}")
        return "; ".join(parts)


@dataclass
class Assembled:
    ctx: dict[str, Any]
    inputs_hash: str
    #: section name → estimated tokens (after trimming)
    sections: dict[str, int]
    #: what was cut to fit the budget, in order
    trimmed: list[str]

    @property
    def tokens(self) -> int:
        return sum(self.sections.values())


def _mentions(data: BookData, text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    chars = {c.key: c for c in data.characters.values()}
    lore = {x.key: x for x in data.lore.values()}
    for kind, key in refs.mentions(text):
        target: Character | LoreEntry | None = None
        if kind in (None, "character") and key in chars:
            target, k = chars[key], "character"
        elif kind in (None, "lore") and key in lore:
            target, k = lore[key], "lore"
        if target is None or (k, key) in seen:
            continue
        seen.add((k, key))
        body = (
            target.body
            if isinstance(target, LoreEntry)
            else " ".join(x for x in (target.role, target.appearance) if x)
        )
        out.append({"name": target.name, "kind": k, "text": _clip(body, 400)})
    return out


def assemble(data: BookData, variant_id: str, *, budget: int = 6000, notes: str = "") -> Assembled:
    node, variant = data.variant(variant_id)
    act = data.acts.get(node.act_id)
    style = _style(data.series.style, data.book.style_overrides, node.style_override)
    location = data.lore.get(node.location_id or "")
    present = sorted(
        (
            data.characters[c.character_id]
            for c in node.characters
            if c.character_id in data.characters
        ),
        key=lambda c: c.name.lower(),
    )

    story: list[str] = []
    seen = {node.id}
    cur = data.predecessor(node)
    while cur is not None and cur.id not in seen and len(story) < STORY_HOPS:
        seen.add(cur.id)
        summary = data.node_summary(cur)
        if summary:
            story.append(f"{cur.title}: {summary}")
        cur = data.predecessor(cur)
    story.reverse()

    pred = data.predecessor(node)
    pred_text = data.node_text(pred) if pred else None
    previous_text = None
    previous_hashed: str | None = None
    if pred_text is not None:
        text, approved = pred_text
        previous_text = text if approved else f"(unapproved draft)\n{text}"
        previous_hashed = text  # the text itself, approved or not (no draft marker)

    choices = [c.label for c in node.choices if c.label]
    encounters = sorted(
        {
            data.enemy_names[x.enemy_id]
            for e in node.encounters
            for x in e.enemies
            if x.enemy_id in data.enemy_names
        }
    )
    items_here = sorted(
        {
            data.item_names[item_id]
            for item_id in [p.item_id for p in node.items] + [p.item_id for p in node.shop_items]
            if item_id in data.item_names
        }
    )
    ctx: dict[str, Any] = {
        "style": style,
        "book": {"title": data.book.title},
        "act": {"title": act.title if act else "", "summary": act.summary if act else ""},
        "beats": [
            {"title": b.title, "description": b.description}
            for b in data.beats_by_node.get(node.id, [])
        ],
        "node": {
            "title": node.title,
            "beat_notes": node.beat_notes,
            "ending": node.ending_kind,
        },
        "variant": {"label": variant.label, "condition": variant.condition},
        "digest": {
            "must_text": data.facts_text(node.id, "must"),
            "may_text": data.facts_text(node.id, "may"),
        },
        "location": {"name": location.name, "text": _clip(location.body)} if location else None,
        "characters": [
            {
                "name": c.name,
                "role": c.role,
                "lines": [
                    f"{label}: {_clip(value, 400)}"
                    for label, value in (
                        ("Appearance", c.appearance),
                        ("Voice", c.voice),
                        ("Motivations", c.motivations),
                    )
                    if value
                ],
            }
            for c in present
        ],
        "mentioned": _mentions(data, node.beat_notes),
        "story_so_far": story,
        "previous_title": pred.title if pred else None,
        "previous_text": previous_text,
        "choices": choices,
        "encounters": encounters,
        "items_here": items_here,
    }

    # What decides staleness: everything except the far-back path summaries
    # (upstream changes reach a node through its predecessor's text, one hop at a time).
    # The predecessor's text counts, but not its status: approving a draft unchanged
    # must not make the sections after it stale.
    hashed = {k: v for k, v in ctx.items() if k not in ("story_so_far", "previous_text")}
    hashed["previous_hashed"] = previous_hashed
    inputs_hash = hashlib.sha256(
        json.dumps(hashed, sort_keys=True, default=str).encode()
    ).hexdigest()

    trimmed = _fit(ctx, budget)
    sections = {k: estimate_tokens(json.dumps(v, default=str)) for k, v in ctx.items() if v}
    ctx_with_notes = {**ctx}
    if notes:
        sections["notes"] = estimate_tokens(notes)
    return Assembled(
        ctx=ctx_with_notes, inputs_hash=inputs_hash, sections=sections, trimmed=trimmed
    )


def _size(ctx: dict[str, Any]) -> int:
    return estimate_tokens(json.dumps(ctx, default=str))


def _fit(ctx: dict[str, Any], budget: int) -> list[str]:
    """Trim lowest-priority context until it fits ``budget`` tokens."""
    trimmed: list[str] = []
    steps: list[tuple[str, Any]] = [
        ("mentioned", lambda: ctx.update(mentioned=[])),
        ("story so far (oldest)", None),
        ("beats", lambda: ctx.update(beats=[])),
        ("character details", lambda: [c.update(lines=c["lines"][:1]) for c in ctx["characters"]]),
        (
            "location text",
            lambda: (
                ctx["location"] and ctx["location"].update(text=_clip(ctx["location"]["text"], 200))
            ),
        ),
        ("previous section (start)", None),
    ]
    for name, action in steps:
        if _size(ctx) <= budget:
            break
        if name == "story so far (oldest)":
            while ctx["story_so_far"] and _size(ctx) > budget:
                ctx["story_so_far"].pop(0)
                trimmed.append(name)
            continue
        if name == "previous section (start)":
            text = ctx.get("previous_text") or ""
            if not text:
                continue
            while _size(ctx) > budget and len(text) >= 8:
                text = text[len(text) // 4 :]
                ctx["previous_text"] = "…" + text
            if _size(ctx) > budget:
                ctx["previous_text"] = None  # still over: the untrimmable parts are too big
            trimmed.append(name)
            continue
        assert action is not None
        action()
        trimmed.append(name)
    return list(dict.fromkeys(trimmed))
