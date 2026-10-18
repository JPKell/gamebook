"""Prose versions, review, the writing queue and the writer → critic → editor pipeline."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.core.analysis.problems import Problem
from gamebook.core.model import BookSnapshot
from gamebook.db.base import utcnow
from gamebook.db.models import Act, Book, Job, Node, PipelineRun, ProseVersion, TextVariant
from gamebook.db.session import Database
from gamebook.jobs import JobCancelledError, JobContext, JobRunner
from gamebook.llm.client import LlmError
from gamebook.llm.templates import CRITIC_SCHEMA, RUBRIC
from gamebook.schemas.llm import WritingSettings
from gamebook.schemas.writing import (
    ActGenerateIn,
    ApproveIn,
    ContextOut,
    GenerateIn,
    NodeProse,
    ProseCreate,
    ProseOut,
    ProseStatus,
    QueueOut,
    QueueRow,
    RejectIn,
    VariantProse,
)
from gamebook.services import llm
from gamebook.services.common import require
from gamebook.services.errors import ConflictError, InvalidError, ServiceError
from gamebook.services.writing_context import Assembled, BookData, assemble


def first_sentences(text: str, n: int = 2) -> str:
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    return " ".join(parts[:n])[:600]


def _variant(session: Session, variant_id: str) -> tuple[TextVariant, Node]:
    v = require(session, TextVariant, variant_id)
    return v, require(session, Node, v.node_id)


def _status(data: BookData, variant_id: str, current_hash: str | None) -> ProseStatus:
    versions = data.prose.get(variant_id, [])
    approved = data.approved(variant_id)
    review = next((p for p in versions if p.status == "in_review"), None)
    if review is not None and (approved is None or review.created_at > approved.created_at):
        return "in_review"
    if approved is not None:
        return "stale" if current_hash and approved.inputs_hash != current_hash else "approved"
    if any(p.status == "draft" for p in versions):
        return "draft"
    return "none"


def _budget(settings: WritingSettings) -> int:
    return settings.context_tokens


# ── reading ──────────────────────────────────────────────────────────────


def node_prose(session: Session, node_id: str) -> NodeProse:
    node = require(session, Node, node_id)
    data = BookData.load(session, node.book_id)
    settings = llm.writing_settings(session, data.series.id)
    out: list[VariantProse] = []
    for v in data.nodes[node.id].variants:
        versions = data.prose.get(v.id, [])
        approved = data.approved(v.id)
        current = assemble(data, v.id, budget=_budget(settings)).inputs_hash if approved else None
        out.append(
            VariantProse(
                variant_id=v.id,
                label=v.label,
                condition=v.condition,
                status=_status(data, v.id, current),
                approved=ProseOut.model_validate(approved) if approved else None,
                latest=ProseOut.model_validate(versions[0]) if versions else None,
                versions=[ProseOut.model_validate(p) for p in versions],
            )
        )
    return NodeProse(node_id=node.id, variants=out)


def context(session: Session, variant_id: str) -> ContextOut:
    _v, node = _variant(session, variant_id)
    data = BookData.load(session, node.book_id)
    settings = llm.writing_settings(session, data.series.id)
    a = assemble(data, variant_id, budget=_budget(settings))
    return ContextOut(
        ctx=a.ctx,
        sections=a.sections,
        tokens=a.tokens,
        budget=_budget(settings),
        trimmed=a.trimmed,
        inputs_hash=a.inputs_hash,
    )


def _ordered(data: BookData) -> list[tuple[Node, TextVariant]]:
    acts = {a.id: a.position for a in data.acts.values()}

    def key(n: Node) -> tuple[int, float, str]:
        nd = data.digest.nodes.get(n.id)
        depth = nd.depth_min if nd and nd.depth_min is not None else float("inf")
        return (acts.get(n.act_id, 0), depth, n.title.lower())

    return [(n, v) for n in sorted(data.nodes.values(), key=key) for v in n.variants]


def queue(session: Session, book_id: str) -> QueueOut:
    data = BookData.load(session, book_id)
    settings = llm.writing_settings(session, data.series.id)
    rows: list[QueueRow] = []
    counts: dict[str, int] = {"none": 0, "draft": 0, "in_review": 0, "approved": 0, "stale": 0}
    for i, (n, v) in enumerate(_ordered(data)):
        approved = data.approved(v.id)
        current = assemble(data, v.id, budget=_budget(settings)).inputs_hash if approved else None
        status = _status(data, v.id, current)
        counts[status] += 1
        latest = data.latest(v.id)
        text = approved.text if approved else (latest.text if latest else "")
        act = data.acts.get(n.act_id)
        nd = data.digest.nodes.get(n.id)
        rows.append(
            QueueRow(
                node_id=n.id,
                node_title=n.title,
                act_id=n.act_id,
                act_title=act.title if act else "",
                variant_id=v.id,
                variant_label=v.label,
                status=status,
                order=i,
                reachable=bool(nd and nd.reachable),
                words=len(text.split()),
                latest_id=latest.id if latest else None,
            )
        )
    return QueueOut(rows=rows, counts=counts)


def stale_problems(
    session: Session, book_id: str, snap: BookSnapshot | None = None
) -> list[Problem]:
    """'Prose stale' (info) for approved text whose context has changed."""
    if not session.scalar(
        select(ProseVersion.id)
        .where(ProseVersion.book_id == book_id, ProseVersion.status == "approved")
        .limit(1)
    ):
        return []  # nothing approved yet: skip loading the book
    out = []
    for n, v in stale_variants(session, book_id, snap):
        label = "" if v.label == "Default" else f" ({v.label})"
        out.append(
            Problem(
                severity="info",
                code="prose_stale",
                message=f"The approved prose for '{n.title}'{label} is out of date with its "
                "beat notes, lore or the section before it",
                act_id=n.act_id,
                node_id=n.id,
            )
        )
    return out


def stale_variants(
    session: Session, book_id: str, snap: BookSnapshot | None = None
) -> list[tuple[Node, TextVariant]]:
    data = BookData.load(session, book_id, snap)
    settings = llm.writing_settings(session, data.series.id)
    out = []
    for n, v in _ordered(data):
        approved = data.approved(v.id)
        if (
            approved is not None
            and approved.inputs_hash != assemble(data, v.id, budget=_budget(settings)).inputs_hash
        ):
            out.append((n, v))
    return out


# ── review actions ───────────────────────────────────────────────────────


def _current_hash(session: Session, node: Node, variant_id: str) -> str:
    data = BookData.load(session, node.book_id)
    settings = llm.writing_settings(session, data.series.id)
    return assemble(data, variant_id, budget=_budget(settings)).inputs_hash


def _supersede_approved(session: Session, variant_id: str, keep: str) -> None:
    for p in session.scalars(
        select(ProseVersion).where(
            ProseVersion.variant_id == variant_id, ProseVersion.status == "approved"
        )
    ):
        if p.id != keep:
            p.status = "superseded"


def write_prose(session: Session, variant_id: str, data: ProseCreate) -> ProseVersion:
    """The author writes (or pastes) prose by hand."""
    v, node = _variant(session, variant_id)
    latest = session.scalar(
        select(ProseVersion)
        .where(ProseVersion.variant_id == variant_id)
        .order_by(ProseVersion.created_at.desc())
        .limit(1)
    )
    pv = ProseVersion(
        book_id=node.book_id,
        node_id=node.id,
        variant_id=v.id,
        text=data.text.strip(),
        status="approved" if data.approve else "draft",
        source="human",
        parent_id=latest.id if latest else None,
        summary=data.summary or first_sentences(data.text),
        inputs_hash=_current_hash(session, node, v.id),
        approved_at=utcnow() if data.approve else None,
    )
    session.add(pv)
    session.flush()
    if data.approve:
        _supersede_approved(session, v.id, pv.id)
    return pv


def approve(session: Session, prose_id: str, data: ApproveIn) -> ProseVersion:
    pv = require(session, ProseVersion, prose_id)
    node = require(session, Node, pv.node_id)
    current = _current_hash(session, node, pv.variant_id)
    target = pv
    edited = data.text is not None and data.text.strip() != pv.text.strip()
    restoring = pv.status in ("superseded", "rejected")
    if edited or restoring:
        # Edits, or bringing back an older version, make a new version so history
        # stays a straight line of what was approved when.
        text = (data.text or pv.text).strip()
        target = ProseVersion(
            book_id=pv.book_id,
            node_id=pv.node_id,
            variant_id=pv.variant_id,
            text=text,
            source="human",
            parent_id=pv.id,
            summary=data.summary
            if data.summary is not None
            else (pv.summary if not edited and pv.summary else first_sentences(text)),
            pipeline_run_id=pv.pipeline_run_id,
        )
        session.add(target)
        if pv.status in ("in_review", "draft"):
            pv.status = "superseded"
    elif data.summary is not None:
        target.summary = data.summary
    target.status = "approved"
    target.approved_at = utcnow()
    target.inputs_hash = current  # approving asserts it fits today's context
    session.flush()
    _supersede_approved(session, target.variant_id, target.id)
    return target


def reject(session: Session, prose_id: str, data: RejectIn) -> ProseVersion:
    pv = require(session, ProseVersion, prose_id)
    if pv.status not in ("in_review", "draft"):
        raise ConflictError(
            f"Only drafts and versions in review can be rejected (this one is {pv.status})"
        )
    pv.status = "rejected"
    pv.notes = data.notes
    session.flush()
    return pv


def update_summary(session: Session, prose_id: str, summary: str) -> ProseVersion:
    pv = require(session, ProseVersion, prose_id)
    pv.summary = summary.strip()
    session.flush()
    return pv


# ── pipeline ─────────────────────────────────────────────────────────────


def _score(report: dict[str, Any]) -> float | None:
    overall = report.get("overall")
    if isinstance(overall, (int, float)):
        return float(overall)
    scores = [
        v
        for k, v in (report.get("scores") or {}).items()
        if k in RUBRIC and isinstance(v, (int, float))
    ]
    return sum(scores) / len(scores) if scores else None


def run_variant(
    db: Database,
    variant_id: str,
    *,
    notes: str = "",
    job: JobContext | None = None,
) -> dict[str, Any]:
    """Writer → critic → (editor → critic)… for one variant. Leaves a version in review."""
    with db.session() as s:
        _v, node = _variant(s, variant_id)
        data = BookData.load(s, node.book_id)
        settings = llm.writing_settings(s, data.series.id)
        a: Assembled = assemble(data, variant_id, budget=_budget(settings), notes=notes)
        run = PipelineRun(
            book_id=node.book_id,
            node_id=node.id,
            variant_id=variant_id,
            job_id=job.job_id if job else None,
            notes=notes,
        )
        s.add(run)
        s.flush()
        run_id, series_id, book_id, node_id = run.id, data.series.id, node.book_id, node.id
    scope = llm.CallScope(
        series_id=series_id,
        book_id=book_id,
        node_id=node_id,
        job_id=job.job_id if job else None,
        pipeline_run_id=run_id,
    )
    trail: list[dict[str, Any]] = []
    cost = 0.0
    final: float | None = None
    iterations = 0

    def save(status: str, error: str | None = None) -> None:
        with db.session() as s:
            r = require(s, PipelineRun, run_id)
            r.trail, r.cost_usd, r.final_score = trail, round(cost, 6), final
            r.iterations, r.status, r.error = iterations, status, error
            if status != "running":
                r.finished_at = utcnow()

    def check() -> None:
        if job is not None:
            job.check()

    base = {"ctx": a.ctx, "notes": notes}
    try:
        res = llm.call(db, role="writer", variables=base, settings=settings, scope=scope)
        cost += res.cost_usd
        draft = res.text
        trail.append({"kind": "draft", "text": draft, "call_id": res.call_id})
        save("running")
        while True:
            check()
            report, res = llm.call_json(
                db,
                role="critic",
                variables={**base, "draft": draft},
                settings=settings,
                scope=scope,
                json_schema=CRITIC_SCHEMA,
            )
            cost += res.cost_usd
            final = _score(report)
            trail.append(
                {"kind": "critique", "report": report, "score": final, "call_id": res.call_id}
            )
            save("running")
            passed = final is not None and final >= settings.pass_threshold
            if passed or iterations >= settings.max_iterations:
                break
            check()
            issues = [i for i in report.get("issues") or [] if isinstance(i, dict)]
            res = llm.call(
                db,
                role="editor",
                variables={**base, "draft": draft, "issues": issues},
                settings=settings,
                scope=scope,
            )
            cost += res.cost_usd
            draft = res.text
            iterations += 1
            trail.append({"kind": "edit", "text": draft, "call_id": res.call_id})
            save("running")
        check()
        try:
            res = llm.call(
                db,
                role="summarizer",
                variables={"ctx": a.ctx, "text": draft},
                settings=settings,
                scope=scope,
            )
            cost += res.cost_usd
            summary = res.text
        except LlmError:
            summary = first_sentences(draft)
    except LlmError as exc:
        save("failed", str(exc))
        raise LlmError(str(exc), cost_usd=cost + exc.cost_usd) from exc
    except ServiceError as exc:  # e.g. a role's provider was disabled mid-run
        save("failed", exc.message)
        raise LlmError(exc.message, cost_usd=cost) from exc
    except JobCancelledError:
        save("cancelled")
        raise
    except Exception as exc:
        save("failed", str(exc))
        raise
    with db.session() as s:
        for old in s.scalars(
            select(ProseVersion).where(
                ProseVersion.variant_id == variant_id, ProseVersion.status == "in_review"
            )
        ):
            old.status = "superseded"
        latest = s.scalar(
            select(ProseVersion)
            .where(ProseVersion.variant_id == variant_id)
            .order_by(ProseVersion.created_at.desc())
            .limit(1)
        )
        pv = ProseVersion(
            book_id=book_id,
            node_id=node_id,
            variant_id=variant_id,
            text=draft,
            status="in_review",
            source="llm",
            pipeline_run_id=run_id,
            parent_id=latest.id if latest else None,
            inputs_hash=a.inputs_hash,
            summary=summary,
            notes=notes,
        )
        s.add(pv)
        s.flush()
        prose_id = pv.id
    save("done")
    return {
        "prose_id": prose_id,
        "pipeline_run_id": run_id,
        "score": final,
        "cost_usd": round(cost, 6),
    }


def _check_ready(session: Session, series_id: str) -> None:
    settings = llm.writing_settings(session, series_id)
    llm.resolve_role(session, settings, "writer")


def _busy(session: Session, variant_ids: set[str]) -> bool:
    """Is a generation job already queued or running for any of these variants?"""
    for job in session.scalars(
        select(Job).where(
            Job.kind.in_(("write", "write_act")), Job.status.in_(("queued", "running"))
        )
    ):
        p = job.payload or {}
        if p.get("variant_id") in variant_ids or variant_ids & set(p.get("variants", [])):
            return True
    return False


def start_variant(session: Session, runner: JobRunner, variant_id: str, data: GenerateIn) -> Job:
    v, node = _variant(session, variant_id)
    if _busy(session, {variant_id}):
        raise ConflictError("This section is already being written")
    book = require(session, Book, node.book_id)
    _check_ready(session, book.series_id)
    job = Job(
        kind="write",
        label=f"Write '{node.title}'" + (f" ({v.label})" if v.label != "Default" else ""),
        total=1,
        payload={"book_id": book.id, "node_id": node.id, "variant_id": v.id},
    )
    session.add(job)
    session.flush()
    session.commit()
    db = runner.db

    def body(ctx: JobContext) -> dict[str, Any]:
        result = run_variant(db, variant_id, notes=data.notes, job=ctx)
        ctx.progress(1, 1, force=True)
        return result

    runner.submit(job.id, body)
    return job


def start_act(session: Session, runner: JobRunner, act_id: str, data: ActGenerateIn) -> Job:
    act = require(session, Act, act_id)
    book = require(session, Book, act.book_id)
    _check_ready(session, book.series_id)
    bd = BookData.load(session, book.id)
    settings = llm.writing_settings(session, book.series_id)
    targets: list[str] = []
    for n, v in _ordered(bd):
        if n.act_id != act_id:
            continue
        approved = bd.approved(v.id)
        current = assemble(bd, v.id, budget=_budget(settings)).inputs_hash if approved else None
        status = _status(bd, v.id, current)
        if (
            data.only == "all"
            or (data.only == "missing" and status in ("none", "draft"))
            or (data.only == "stale" and status == "stale")
        ):
            targets.append(v.id)
    if not targets:
        raise InvalidError("Nothing in this act matches; try another filter")
    if _busy(session, set(targets)):
        raise ConflictError("Some of these sections are already being written")
    job = Job(
        kind="write_act",
        label=f"Write {act.title} ({len(targets)} section{'s' if len(targets) != 1 else ''})",
        total=len(targets),
        payload={"book_id": book.id, "act_id": act.id, "variants": targets},
    )
    session.add(job)
    session.flush()
    session.commit()
    db = runner.db
    budget = data.max_cost_usd

    def body(ctx: JobContext) -> dict[str, Any]:
        spent, done, failed = 0.0, 0, []
        stopped = None
        for i, vid in enumerate(targets):
            ctx.check()
            if budget is not None and spent >= budget:
                stopped = f"Stopped at the ${budget:.2f} budget"
                break
            try:
                spent += run_variant(db, vid, job=ctx)["cost_usd"]
                done += 1
            except LlmError as exc:
                spent += exc.cost_usd  # calls that succeeded before the failure still cost
                failed.append({"variant_id": vid, "error": str(exc)})
            ctx.progress(i + 1, len(targets), force=True)
        return {"written": done, "failed": failed, "cost_usd": round(spent, 6), "stopped": stopped}

    runner.submit(job.id, body)
    return job


def pipeline_run(session: Session, run_id: str) -> PipelineRun:
    return require(session, PipelineRun, run_id)
