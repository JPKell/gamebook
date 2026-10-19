"""LLM authoring assists (SPEC §5.3): consistency checker, beat/branch suggester, lore extractor.

Each runs as a job and leaves ``AssistItem`` rows for the author to act on:
findings show in the Problems panel, suggestions as a draft subgraph on the
canvas, lore drafts in the Lore section.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.core.analysis.problems import Problem
from gamebook.db.models import (
    Act,
    AssistItem,
    Book,
    Character,
    Choice,
    Job,
    LoreEntry,
    Node,
    ProseVersion,
)
from gamebook.db.repository import NotFoundError
from gamebook.db.session import Database
from gamebook.jobs import JobContext, JobRunner
from gamebook.llm.client import LlmError
from gamebook.llm.templates import CONSISTENCY_SCHEMA, LORE_SCHEMA, SUGGESTER_SCHEMA
from gamebook.schemas.assist import AcceptLoreIn, AcceptSuggestionIn, RejectSuggestionIn
from gamebook.schemas.entities import CharacterCreate, CharacterUpdate, LoreCreate, LoreUpdate
from gamebook.schemas.node import ChoiceCreate, NodeCreate
from gamebook.services import entities, history, llm, nodes
from gamebook.services.common import require
from gamebook.services.errors import ConflictError, InvalidError
from gamebook.services.writing_context import BookData, assemble

LORE_TYPES = {"location", "faction", "history", "glossary", "other"}
CHARACTER_FIELDS = ("role", "appearance", "voice", "motivations", "secrets", "notes")
#: Cap on approved prose sent to the lore extractor in one call (characters).
LORE_CHARS = 24_000
#: Caps on what one model reply can propose (a runaway reply mustn't flood the book).
MAX_ISSUES = 20
MAX_NEW_NODES = 20
MAX_NEW_CHOICES = 40
MAX_LORE_ROWS = 30
TEXT_CAP = 4000


def _text(value: Any, cap: int = TEXT_CAP) -> str:
    """A model-supplied value as bounded text (models return all sorts)."""
    return str(value or "")[:cap] if isinstance(value, (str, int, float)) else ""


def free_spot(pos: tuple[float, float], taken: list[tuple[float, float]]) -> tuple[float, float]:
    """The first spot at or below ``pos`` that doesn't overlap a card (240 x 110 + margins)."""
    x, y = pos
    for _ in range(200):
        if not any(abs(tx - x) < 260 and abs(ty - y) < 130 for tx, ty in taken):
            break
        y += 140
    return x, y


def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()


def _scope(
    series_id: str, book_id: str, job: JobContext, node_id: str | None = None
) -> llm.CallScope:
    return llm.CallScope(series_id=series_id, book_id=book_id, node_id=node_id, job_id=job.job_id)


def _job(session: Session, kind: str, label: str, total: int, payload: dict[str, Any]) -> Job:
    job = Job(kind=kind, label=label, total=total, payload=payload)
    session.add(job)
    session.flush()
    return job


def _ready(session: Session, series_id: str, role: str) -> None:
    llm.resolve_role(session, llm.writing_settings(session, series_id), role)


# ── consistency ──────────────────────────────────────────────────────────


def _prose_for(data: BookData, variant_id: str) -> ProseVersion | None:
    approved = data.approved(variant_id)
    if approved is not None:
        return approved
    return next(
        (p for p in data.prose.get(variant_id, []) if p.status in ("in_review", "draft")), None
    )


def check_node(db: Database, node_id: str, job: JobContext, data: BookData | None = None) -> int:
    """Check every variant of a node that has prose. Returns how many issues were found.

    ``data`` is the book, loaded once per job; it must still contain the node.
    """
    with db.session() as s:
        node = require(s, Node, node_id)
        if data is None or node_id not in data.nodes:
            data = BookData.load(s, node.book_id)
        settings = llm.writing_settings(s, data.series.id)
        work = []
        for v in data.nodes[node_id].variants:
            pv = _prose_for(data, v.id)
            if pv is not None:
                a = assemble(data, v.id, budget=settings.context_tokens)
                work.append((v.id, v.label, pv.text, a.ctx))
        series_id, book_id = data.series.id, node.book_id
    found = 0
    for variant_id, label, text, ctx in work:
        job.check()
        report, res = llm.call_json(
            db,
            role="consistency",
            variables={"ctx": ctx, "prose": text, "notes": ""},
            settings=settings,
            scope=_scope(series_id, book_id, job, node_id),
            json_schema=CONSISTENCY_SCHEMA,
        )
        issues = [
            i for i in report.get("issues") or [] if isinstance(i, dict) and _text(i.get("problem"))
        ][:MAX_ISSUES]
        checked = text_hash(text)
        with db.session() as s:
            # Findings the author dismissed for this exact prose stay dismissed.
            dismissed = {
                d.payload.get("problem")
                for d in s.scalars(
                    select(AssistItem).where(
                        AssistItem.kind == "finding",
                        AssistItem.node_id == node_id,
                        AssistItem.status == "dismissed",
                        AssistItem.checked_hash == checked,
                    )
                )
                if d.payload.get("variant_id") == variant_id
            }
            issues = [i for i in issues if _text(i["problem"]) not in dismissed]
            for old in s.scalars(
                select(AssistItem).where(
                    AssistItem.kind == "finding",
                    AssistItem.node_id == node_id,
                    AssistItem.status == "open",
                )
            ):
                if old.payload.get("variant_id") == variant_id:
                    old.status = "superseded"
            for i in issues:
                s.add(
                    AssistItem(
                        book_id=book_id,
                        kind="finding",
                        node_id=node_id,
                        payload={
                            "variant_id": variant_id,
                            "variant_label": label,
                            "severity": "info" if i.get("severity") == "info" else "warning",
                            "category": _text(i.get("kind"), 32) or "other",
                            "quote": _text(i.get("quote"), 1000),
                            "problem": _text(i["problem"]),
                            "suggestion": _text(i.get("suggestion")),
                        },
                        checked_hash=checked,
                        job_id=job.job_id,
                        call_id=res.call_id,
                    )
                )
        found += len(issues)
    return found


def start_consistency(
    session: Session,
    runner: JobRunner,
    *,
    book_id: str,
    node_id: str | None = None,
    act_id: str | None = None,
) -> Job:
    book = require(session, Book, book_id)
    _ready(session, book.series_id, "consistency")
    if node_id is not None:
        node_ids = [node_id]
        label = f"Check '{require(session, Node, node_id).title}'"
    else:
        with_prose = set(
            session.scalars(
                select(ProseVersion.node_id).where(
                    ProseVersion.book_id == book_id,
                    ProseVersion.status.in_(("approved", "in_review", "draft")),
                )
            )
        )
        q = select(Node).where(Node.book_id == book_id)
        if act_id is not None:
            act = require(session, Act, act_id)
            if act.book_id != book_id:
                raise InvalidError("That act belongs to another book", field="act_id")
            q = q.where(Node.act_id == act_id)
        node_ids = [n.id for n in session.scalars(q.order_by(Node.title)) if n.id in with_prose]
        label = "Check consistency" + (f": {require(session, Act, act_id).title}" if act_id else "")
    if not node_ids:
        raise InvalidError("Nothing to check: no section here has prose yet")
    job = _job(
        session, "consistency", label, len(node_ids), {"book_id": book_id, "nodes": node_ids}
    )
    session.commit()
    db = runner.db

    def body(ctx: JobContext) -> dict[str, Any]:
        issues, failed = 0, []
        with db.session() as s:
            data = BookData.load(s, book_id)  # once per job, not once per section
        for i, nid in enumerate(node_ids):
            ctx.check()
            try:
                issues += check_node(db, nid, ctx, data)
            except LlmError as exc:
                failed.append({"node_id": nid, "error": str(exc)})
            except NotFoundError:
                failed.append({"node_id": nid, "error": "The section was deleted"})
            ctx.progress(i + 1, len(node_ids), force=True)
        return {"issues": issues, "checked": len(node_ids) - len(failed), "failed": failed}

    runner.submit(job.id, body)
    return job


def finding_problems(session: Session, book_id: str) -> list[Problem]:
    """Open findings whose prose hasn't changed since the check (shown in Problems)."""
    items = list(
        session.scalars(
            select(AssistItem).where(
                AssistItem.book_id == book_id,
                AssistItem.kind == "finding",
                AssistItem.status == "open",
            )
        )
    )
    if not items:
        return []
    current = _current_hashes(session, book_id)
    out = []
    for it in items:
        if current.get(it.payload.get("variant_id", "")) != it.checked_hash:
            continue
        node = session.get(Node, it.node_id or "")
        if node is None:
            continue
        quote = it.payload.get("quote")
        out.append(
            Problem(
                severity="info" if it.payload.get("severity") == "info" else "warning",
                code="consistency",
                message=(f'"{quote}": ' if quote else "") + it.payload.get("problem", ""),
                act_id=node.act_id,
                node_id=node.id,
            )
        )
    return out


def _current_hashes(session: Session, book_id: str) -> dict[str, str]:
    """variant id → hash of the prose a check would read now."""
    best: dict[str, ProseVersion] = {}
    for pv in session.scalars(
        select(ProseVersion)
        .where(
            ProseVersion.book_id == book_id,
            ProseVersion.status.in_(("approved", "in_review", "draft")),
        )
        .order_by(ProseVersion.created_at)
    ):
        cur = best.get(pv.variant_id)
        if cur is None or cur.status != "approved" or pv.status == "approved":
            best[pv.variant_id] = pv
    return {k: text_hash(v.text) for k, v in best.items()}


def list_items(
    session: Session, book_id: str, kind: str | None, status: str | None, node_id: str | None
) -> list[dict[str, Any]]:
    require(session, Book, book_id)
    q = select(AssistItem).where(AssistItem.book_id == book_id)
    if kind:
        q = q.where(AssistItem.kind == kind)
    if status:
        q = q.where(AssistItem.status == status)
    if node_id:
        q = q.where(AssistItem.node_id == node_id)
    items = list(session.scalars(q.order_by(AssistItem.created_at.desc())))
    acts = set(session.scalars(select(Act.id).where(Act.book_id == book_id)))
    live_nodes = set(session.scalars(select(Node.id).where(Node.book_id == book_id)))
    for i in items:
        if i.kind == "suggestion" and i.status in ("open", "partial") and i.act_id not in acts:
            i.status = "superseded"  # its act was deleted
    items = [
        i
        for i in items
        if (i.kind != "finding" or i.node_id in live_nodes) and (not status or i.status == status)
    ]
    current = _current_hashes(session, book_id) if any(i.kind == "finding" for i in items) else {}
    return [
        {
            **{
                c: getattr(i, c)
                for c in (
                    "id",
                    "book_id",
                    "kind",
                    "status",
                    "node_id",
                    "act_id",
                    "payload",
                    "created_at",
                )
            },
            "outdated": i.kind == "finding"
            and current.get(i.payload.get("variant_id", "")) != i.checked_hash,
        }
        for i in items
    ]


#: (kind, from, to) moves allowed through PATCH; everything else has its own endpoint.
_MOVES = {
    ("finding", "open", "dismissed"),
    ("finding", "dismissed", "open"),
    ("lore", "open", "rejected"),
}


def set_status(session: Session, item_id: str, status: str) -> AssistItem:
    item = require(session, AssistItem, item_id)
    if (item.kind, item.status, status) not in _MOVES:
        raise ConflictError(f"A {item.kind} that is {item.status} can't become {status}")
    item.status = status
    session.flush()
    return item


# ── suggester ────────────────────────────────────────────────────────────


def _clip(text: str, n: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def suggest_variables(data: BookData, act_id: str, notes: str) -> dict[str, Any]:
    act = data.acts[act_id]
    by_id = data.nodes
    titles = {n.id: n.title for n in by_id.values()}
    act_nodes = sorted((n for n in by_id.values() if n.act_id == act_id), key=lambda n: n.title)
    nodes_v = []
    for n in act_nodes:
        flags = [f for f, on in (("entry", n.is_act_entry), ("exit", n.is_act_exit)) if on] + (
            [f"ending:{n.ending_kind}"] if n.ending_kind else []
        )
        nodes_v.append(
            {
                "key": n.key,
                "title": n.title,
                "flags": ",".join(flags),
                "beat_notes": _clip(n.beat_notes),
                "choices": [
                    {
                        "label": c.label or "(unlabelled)",
                        "to": by_id[o.target_node_id].key
                        if o.target_node_id in by_id
                        else "(nowhere)",
                    }
                    for c in n.choices
                    for o in c.outcomes[:1]
                ],
            }
        )
    return {
        "book": {"title": data.book.title},
        "act": {"title": act.title, "summary": act.summary},
        "beats": [
            {
                "title": b.title,
                "description": b.description,
                "nodes": [titles[x] for x in b.node_ids if x in titles],
            }
            for b in act.beats
        ],
        "nodes": nodes_v,
        "notes": notes,
    }


def _clean_suggestion(
    raw: dict[str, Any], positions: dict[str, tuple[float, float]]
) -> dict[str, Any]:
    """Keep well-formed new sections and choices whose ends exist, within caps, and
    decide where each new section will go (the canvas ghosts and accepting both
    use these positions, so cards don't jump)."""
    keys = set(positions)
    new: list[dict[str, Any]] = []
    refs: set[str] = set()
    for n in (raw.get("nodes") or [])[: MAX_NEW_NODES * 3]:
        if not isinstance(n, dict) or len(new) >= MAX_NEW_NODES:
            continue
        ref, title = _text(n.get("ref"), 64).strip(), _text(n.get("title"), 200).strip()
        if not ref or not title or ref in refs or ref in keys:
            continue
        refs.add(ref)
        new.append(
            {
                "ref": ref,
                "title": title,
                "beat_notes": _text(n.get("beat_notes")),
                "beat": _text(n.get("beat"), 200),
                "status": "pending",
                "node_id": None,
            }
        )
    ends = keys | refs
    choices: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for c in (raw.get("choices") or [])[: MAX_NEW_CHOICES * 3]:
        if not isinstance(c, dict) or len(choices) >= MAX_NEW_CHOICES:
            continue
        a, b = _text(c.get("from"), 64), _text(c.get("to"), 64)
        if a not in ends or b not in ends or a == b or (a, b) in seen:
            continue
        if a in keys and b in keys:
            continue  # only choices that involve a new section are in scope
        seen.add((a, b))
        choices.append(
            {"from": a, "to": b, "label": _text(c.get("label"), 500), "status": "pending"}
        )

    taken = list(positions.values())
    placed: dict[str, tuple[float, float]] = dict(positions)
    right = max((x for x, _ in positions.values()), default=-320.0) + 320
    for n in new:
        source = next(
            (placed[c["from"]] for c in choices if c["to"] == n["ref"] and c["from"] in placed),
            None,
        )
        x, y = free_spot((source[0] + 320, source[1]) if source else (right, 0.0), taken)
        taken.append((x, y))
        placed[n["ref"]] = (x, y)
        n["x"], n["y"] = x, y
    return {"rationale": _text(raw.get("rationale"), 1000), "nodes": new, "choices": choices}


def start_suggest(session: Session, runner: JobRunner, act_id: str, notes: str) -> Job:
    act = require(session, Act, act_id)
    book = require(session, Book, act.book_id)
    _ready(session, book.series_id, "suggester")
    job = _job(
        session,
        "suggest",
        f"Suggest sections: {act.title}",
        1,
        {"book_id": book.id, "act_id": act_id},
    )
    session.commit()
    db = runner.db
    book_id, series_id = book.id, book.series_id

    def body(ctx: JobContext) -> dict[str, Any]:
        with db.session() as s:
            data = BookData.load(s, book_id)
            variables = suggest_variables(data, act_id, notes)
            positions = {n.key: (n.x, n.y) for n in data.nodes.values()}
            settings = llm.writing_settings(s, series_id)
        raw, res = llm.call_json(
            db,
            role="suggester",
            variables=variables,
            settings=settings,
            scope=_scope(series_id, book_id, ctx),
            json_schema=SUGGESTER_SCHEMA,
        )
        ctx.check()  # cancelled while the model was thinking: write nothing
        payload = _clean_suggestion(raw, positions)
        payload["notes"] = notes
        if not payload["nodes"] and not payload["choices"]:
            # Nothing usable: keep any earlier suggestion rather than replacing it.
            ctx.progress(1, 1, force=True)
            return {"item_id": None, "nodes": 0, "choices": 0}
        with db.session() as s:
            for old in s.scalars(
                select(AssistItem).where(
                    AssistItem.kind == "suggestion",
                    AssistItem.act_id == act_id,
                    AssistItem.status.in_(("open", "partial")),
                )
            ):
                old.status = "superseded"
            item = AssistItem(
                book_id=book_id,
                kind="suggestion",
                act_id=act_id,
                payload=payload,
                job_id=ctx.job_id,
                call_id=res.call_id,
            )
            s.add(item)
            s.flush()
            item_id = item.id
        ctx.progress(1, 1, force=True)
        return {
            "item_id": item_id,
            "nodes": len(payload["nodes"]),
            "choices": len(payload["choices"]),
        }

    runner.submit(job.id, body)
    return job


def _settle(item: AssistItem) -> None:
    parts = [*item.payload["nodes"], *item.payload["choices"]]
    pending = [p for p in parts if p["status"] == "pending"]
    accepted = [p for p in parts if p["status"] == "accepted"]
    if pending:
        item.status = "partial" if accepted or len(pending) < len(parts) else "open"
    else:
        item.status = "accepted" if accepted else "rejected"


def _resync(session: Session, item: AssistItem, payload: dict[str, Any]) -> None:
    """Things accepted earlier but gone now (undone or deleted) become pending again."""
    for n in payload["nodes"]:
        if n["status"] == "accepted" and (
            not n.get("node_id") or session.get(Node, n["node_id"]) is None
        ):
            n["status"], n["node_id"] = "pending", None
    for c in payload["choices"]:
        if c["status"] == "accepted" and (
            not c.get("choice_id") or session.get(Choice, c["choice_id"]) is None
        ):
            c["status"] = "pending"
            c.pop("choice_id", None)


def _copy(item: AssistItem) -> dict[str, Any]:
    return {
        **item.payload,
        "nodes": [dict(n) for n in item.payload["nodes"]],
        "choices": [dict(c) for c in item.payload["choices"]],
    }


def accept_suggestion(session: Session, item_id: str, data: AcceptSuggestionIn) -> AssistItem:
    item = require(session, AssistItem, item_id)
    if item.kind != "suggestion" or item.status not in ("open", "partial"):
        raise ConflictError("This suggestion is no longer open")
    if item.act_id is None or session.get(Act, item.act_id) is None:
        item.status = "superseded"  # its act is gone; nothing can be added
        session.flush()
        return item
    payload = _copy(item)
    _resync(session, item, payload)
    want_all = not data.nodes and not data.choices
    node_by_ref = {n["ref"]: n for n in payload["nodes"]}
    choice_idx = {
        i
        for i in (range(len(payload["choices"])) if want_all else data.choices)
        if 0 <= i < len(payload["choices"]) and payload["choices"][i]["status"] == "pending"
    }
    refs = {r for r in (set(node_by_ref) if want_all else set(data.nodes)) if r in node_by_ref}
    for i in choice_idx:  # a choice brings its new end sections with it
        for end in ("from", "to"):
            if payload["choices"][i][end] in node_by_ref:
                refs.add(payload["choices"][i][end])
    to_create = [r for r in sorted(refs) if node_by_ref[r]["status"] == "pending"]
    book = require(session, Book, item.book_id)
    existing = {n.key: n for n in session.scalars(select(Node).where(Node.book_id == book.id))}

    def available(name: str) -> bool:
        n = node_by_ref.get(name)
        if n is not None:
            return n["status"] == "accepted" or name in to_create
        return name in existing

    wired = [
        i
        for i in sorted(choice_idx)
        if available(payload["choices"][i]["from"]) and available(payload["choices"][i]["to"])
    ]
    if not to_create and not wired:
        item.payload = payload
        _settle(item)
        session.flush()
        return item  # nothing to do: no undo entry
    history.record(session, book.id, "Accept suggested sections")

    def node_for(name: str) -> Node | None:
        n = node_by_ref.get(name)
        if n is not None:
            return session.get(Node, n["node_id"]) if n.get("node_id") else None
        return existing.get(name)

    taken = [(n.x, n.y) for n in existing.values()]
    for ref in to_create:
        n = node_by_ref[ref]
        if "x" in n:
            x, y = float(n["x"]), float(n["y"])
        else:
            x, y = free_spot((0.0, 0.0), taken)
        taken.append((x, y))
        created = nodes.create_node(
            session,
            book.id,
            NodeCreate(act_id=item.act_id, title=n["title"], beat_notes=n["beat_notes"], x=x, y=y),
        )
        n["status"], n["node_id"] = "accepted", created.id
    for i in wired:
        c = payload["choices"][i]
        src, dst = node_for(c["from"]), node_for(c["to"])
        if src is None or dst is None:
            continue
        created_choice = nodes.create_choice(
            session, src.id, ChoiceCreate(label=c["label"], target_node_id=dst.id)
        )
        c["status"], c["choice_id"] = "accepted", created_choice.id
    item.payload = payload
    _settle(item)
    session.flush()
    return item


def reject_suggestion(session: Session, item_id: str, data: RejectSuggestionIn) -> AssistItem:
    item = require(session, AssistItem, item_id)
    if item.kind != "suggestion" or item.status not in ("open", "partial"):
        raise ConflictError("This suggestion is no longer open")
    payload = _copy(item)
    _resync(session, item, payload)
    everything = not data.nodes and not data.choices
    pending_refs = {n["ref"] for n in payload["nodes"] if n["status"] == "pending"}
    # Only still-pending sections can be rejected (accepted ones are real nodes now).
    rejected_refs = pending_refs if everything else pending_refs & set(data.nodes)
    for n in payload["nodes"]:
        if n["ref"] in rejected_refs:
            n["status"] = "rejected"
    for i, c in enumerate(payload["choices"]):
        if c["status"] != "pending":
            continue
        ends_gone = c["from"] in rejected_refs or c["to"] in rejected_refs
        if everything or i in data.choices or ends_gone:
            c["status"] = "rejected"
    item.payload = payload
    _settle(item)
    session.flush()
    return item


# ── lore extractor ───────────────────────────────────────────────────────


def start_extract(session: Session, runner: JobRunner, book_id: str, act_id: str | None) -> Job:
    book = require(session, Book, book_id)
    _ready(session, book.series_id, "lore_extractor")
    q = (
        select(ProseVersion, Node)
        .join(Node, Node.id == ProseVersion.node_id)
        .where(ProseVersion.book_id == book_id, ProseVersion.status == "approved")
    )
    if act_id is not None:
        act = require(session, Act, act_id)
        if act.book_id != book_id:
            raise InvalidError("That act belongs to another book", field="act_id")
        q = q.where(Node.act_id == act_id)
    rows = list(session.execute(q.order_by(Node.title)))
    if not rows:
        raise InvalidError("Nothing to read: no approved prose here yet")
    prose, size, skipped = [], 0, 0
    for pv, node in rows:
        if size + len(pv.text) > LORE_CHARS:
            skipped += 1  # too much for one call; read an act at a time for the rest
            continue
        prose.append({"title": node.title, "text": pv.text, "node_id": node.id})
        size += len(pv.text)
    if not prose:
        raise InvalidError("The approved prose is too long to read at once; try one act")
    job = _job(
        session,
        "extract_lore",
        "Extract lore" + (f": {require(session, Act, act_id).title}" if act_id else ""),
        1,
        {"book_id": book_id, "act_id": act_id},
    )
    session.commit()
    db = runner.db
    series_id = book.series_id

    def body(ctx: JobContext) -> dict[str, Any]:
        def visible(model: type[Any]) -> Any:
            # Shared entities and this book's own: never another book's.
            return select(model).where(
                model.series_id == series_id,
                (model.book_id.is_(None)) | (model.book_id == book_id),
            )

        with db.session() as s:
            chars = list(s.scalars(visible(Character)))
            lore = list(s.scalars(visible(LoreEntry)))
            existing = [{"kind": "character", "key": c.key, "name": c.name} for c in chars] + [
                {"kind": "lore", "key": x.key, "name": x.name} for x in lore
            ]
            char_ids = {c.key: c.id for c in chars}
            lore_ids = {x.key: x.id for x in lore}
            pending = {
                (i.payload.get("target"), i.payload.get("fields", {}).get("name", "").lower())
                for i in s.scalars(
                    select(AssistItem).where(
                        AssistItem.book_id == book_id,
                        AssistItem.kind == "lore",
                        AssistItem.status == "open",
                    )
                )
            }
            settings = llm.writing_settings(s, series_id)
        raw, res = llm.call_json(
            db,
            role="lore_extractor",
            variables={"existing": existing, "prose": prose, "notes": ""},
            settings=settings,
            scope=_scope(series_id, book_id, ctx),
            json_schema=LORE_SCHEMA,
        )
        ctx.check()  # cancelled while the model was reading: write nothing
        created = 0
        with db.session() as s:
            for target, rows_, ids in (
                ("character", raw.get("characters") or [], char_ids),
                ("lore", raw.get("entries") or [], lore_ids),
            ):
                for r in (rows_ if isinstance(rows_, list) else [])[:MAX_LORE_ROWS]:
                    if not isinstance(r, dict) or not _text(r.get("name"), 200).strip():
                        continue
                    name = _text(r["name"], 200).strip()
                    if (target, name.lower()) in pending:
                        continue
                    key = _text(r.get("existing_key"), 64)
                    existing_id = ids.get(key) if key else None
                    if target == "character":
                        fields = {f: _text(r.get(f)) for f in CHARACTER_FIELDS}
                    else:
                        kind = _text(r.get("type"), 16) or "other"
                        fields = {
                            "type": kind if kind in LORE_TYPES else "other",
                            "body": _text(r.get("body")),
                        }
                    s.add(
                        AssistItem(
                            book_id=book_id,
                            kind="lore",
                            act_id=act_id,
                            payload={
                                "target": target,
                                "existing_id": existing_id,
                                "existing_key": key if existing_id else None,
                                "fields": {"name": name, **fields},
                                "evidence": _text(r.get("evidence"), 1000),
                            },
                            job_id=ctx.job_id,
                            call_id=res.call_id,
                        )
                    )
                    pending.add((target, name.lower()))
                    created += 1
        ctx.progress(1, 1, force=True)
        return {"drafts": created, "sections_read": len(prose), "sections_skipped": skipped}

    runner.submit(job.id, body)
    return job


#: The fields a lore draft may set, per target (nothing else can be written).
_LORE_FIELDS = {"character": ("name", *CHARACTER_FIELDS), "lore": ("name", "type", "body")}


def accept_lore(session: Session, item_id: str, data: AcceptLoreIn) -> AssistItem:
    """Create the entity, or add the new facts to the existing one (through the
    normal entity service, so validation and the reference index apply)."""
    item = require(session, AssistItem, item_id)
    if item.kind != "lore" or item.status != "open":
        raise ConflictError("This draft is no longer open")
    book = require(session, Book, item.book_id)
    p = item.payload
    target = p["target"]
    allowed = _LORE_FIELDS["character" if target == "character" else "lore"]
    edits = {k: v for k, v in (data.fields or {}).items() if k in allowed}
    fields = {k: v for k, v in {**p["fields"], **edits}.items() if k in allowed}
    kind = entities.KINDS["character" if target == "character" else "lore"]
    existing_id = p.get("existing_id")
    if existing_id:
        obj: Any = session.get(kind.model, existing_id)
        if obj is None:
            raise ConflictError(
                "The entry this draft updates has been deleted; reject the draft instead"
            )
        merged: dict[str, str] = {}
        for f, value in fields.items():
            if f in ("name", "type") or not value.strip():
                continue
            current = getattr(obj, f, "") or ""
            if value.strip() not in current:
                merged[f] = f"{current}\n\n{value.strip()}".strip()
        if merged:
            update: Any = (
                CharacterUpdate(**merged) if target == "character" else LoreUpdate(**merged)
            )
            entities.update_entity(session, kind, obj.id, update)
    else:
        if target == "character":
            create: Any = CharacterCreate(
                name=fields["name"], **{f: fields.get(f, "") for f in CHARACTER_FIELDS}
            )
        else:
            kind_type = fields.get("type", "other")
            create = LoreCreate(
                name=fields["name"],
                type=kind_type if kind_type in LORE_TYPES else "other",
                body=fields.get("body", ""),
            )
        obj = entities.create_entity(session, kind, book.series_id, create)
    item.status = "accepted"
    item.payload = {**p, "fields": fields, "entity_id": obj.id}
    session.flush()
    return item
