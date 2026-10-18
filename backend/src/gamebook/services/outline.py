"""Act outlines (story beats) and the state digest."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from gamebook.core.analysis.digest import FactKind, NodeDigest, compute
from gamebook.db.models import Act, BeatNode, Book, Node, StoryBeat
from gamebook.schemas.common import Reorder
from gamebook.schemas.outline import (
    BeatCreate,
    BeatUpdate,
    BookDigestOut,
    FactOut,
    FactsOut,
    GateOut,
    NodeDigestOut,
    OutlineAct,
    OutlineOut,
)
from gamebook.services import history, refs, snapshot
from gamebook.services.common import require
from gamebook.services.errors import InvalidError

# ── outline ──────────────────────────────────────────────────────────────


def outline(session: Session, book_id: str) -> OutlineOut:
    require(session, Book, book_id)
    acts = session.scalars(
        select(Act)
        .where(Act.book_id == book_id)
        .order_by(Act.position)
        .options(selectinload(Act.beats).selectinload(StoryBeat.links))
    )
    return OutlineOut(
        book_id=book_id, acts=[OutlineAct.model_validate(a, from_attributes=True) for a in acts]
    )


def _links(session: Session, act: Act, node_ids: list[str]) -> list[BeatNode]:
    ids = list(dict.fromkeys(node_ids))
    if ids:
        found = set(session.scalars(select(Node.id).where(Node.id.in_(ids), Node.act_id == act.id)))
        missing = [i for i in ids if i not in found]
        if missing:
            raise InvalidError("A beat can only link nodes in its own act", field="node_ids")
    return [BeatNode(node_id=nid, position=i) for i, nid in enumerate(ids)]


def create_beat(session: Session, act_id: str, data: BeatCreate) -> StoryBeat:
    act = require(session, Act, act_id)
    history.record(session, act.book_id, f"Add story beat '{data.title}'")
    beat = StoryBeat(
        act_id=act.id,
        position=len(act.beats),
        title=data.title,
        description=data.description,
    )
    beat.links = _links(session, act, data.node_ids)
    session.add(beat)
    session.flush()
    refs.reindex(session, "beat", beat)
    return beat


def update_beat(session: Session, beat_id: str, data: BeatUpdate) -> StoryBeat:
    beat = require(session, StoryBeat, beat_id)
    act = require(session, Act, beat.act_id)
    history.record(session, act.book_id, f"Edit story beat '{beat.title}'")
    if data.title is not None:
        beat.title = data.title
    if data.description is not None:
        beat.description = data.description
    if data.node_ids is not None:
        beat.links = _links(session, act, data.node_ids)
    session.flush()
    refs.reindex(session, "beat", beat)
    return beat


def delete_beat(session: Session, beat_id: str) -> None:
    beat = require(session, StoryBeat, beat_id)
    act = require(session, Act, beat.act_id)
    history.record(session, act.book_id, f"Delete story beat '{beat.title}'")
    refs.drop(session, "beat", [beat.id])
    session.delete(beat)
    session.flush()
    for i, b in enumerate(
        sorted((b for b in act.beats if b.id != beat_id), key=lambda b: b.position)
    ):
        b.position = i


def reorder_beats(session: Session, act_id: str, data: Reorder) -> list[StoryBeat]:
    act = require(session, Act, act_id)
    current = {b.id: b for b in act.beats}
    if sorted(data.ids) != sorted(current):
        raise InvalidError("Send every beat of the act exactly once", field="ids")
    history.record(session, act.book_id, "Reorder story beats")
    for i, bid in enumerate(data.ids):
        current[bid].position = i
    session.flush()
    session.refresh(act)
    return list(act.beats)


# ── state digest ─────────────────────────────────────────────────────────


def _facts(nd: NodeDigest, which: str, labels: dict[FactKind, dict[str, str]]) -> FactsOut:
    def fs(kind: FactKind) -> list[FactOut]:
        return [
            FactOut(key=k, label=labels[kind].get(k, k))
            for k in nd.facts(kind, "must" if which == "must" else "may")
        ]

    return FactsOut(
        flags=fs("flag"), items=fs("item"), characters=fs("character"), skills=fs("skill")
    )


def book_digest(session: Session, book_id: str, tier: str | None) -> BookDigestOut:
    book = snapshot.book_snapshot(session, book_id)
    if book.rules is None:
        raise InvalidError("The series has no active rule system")
    if tier is not None and tier not in book.rules.tier_keys():
        raise InvalidError(f"Unknown tier {tier!r}", field="tier")
    d = compute(book, tier)
    labels: dict[FactKind, dict[str, str]] = {
        "flag": {},
        "item": {i.key: i.name for i in book.items},
        "character": {c.key: c.name for c in book.characters},
        "skill": {},
    }
    for t in book.rules.tiers:
        for sk in t.skills:
            labels["skill"][sk.key] = sk.label
    out: dict[str, NodeDigestOut] = {}
    for n in book.nodes:
        nd = d.nodes[n.id]
        gates = [
            GateOut(
                choice_id=c.id,
                label=c.label,
                condition=c.condition or "",
                verdict={True: "always", False: "never", None: "depends"}[nd.gates[c.id]],
            )
            for c in n.choices
            if c.id in nd.gates
        ]
        out[n.id] = NodeDigestOut(
            node_id=n.id,
            reachable=nd.reachable,
            depth_min=nd.depth_min,
            depth_max=nd.depth_max,
            canonical_predecessor_auto=nd.canonical_predecessor,
            canonical_predecessor_override=n.canonical_predecessor_id,
            canonical_predecessor=n.canonical_predecessor_id or nd.canonical_predecessor,
            must=_facts(nd, "must", labels),
            may=_facts(nd, "may", labels),
            gates=gates,
        )
    return BookDigestOut(tier=d.tier, nodes=out)


def node_digest(session: Session, node_id: str, tier: str | None) -> NodeDigestOut:
    node = require(session, Node, node_id)
    return book_digest(session, node.book_id, tier).nodes[node.id]
