"""Series, rule systems, codewords and where-used."""

from typing import Literal

from fastapi import APIRouter, Query, Request, Response, status

from gamebook.api.deps import SessionDep
from gamebook.core.keys import key_problem
from gamebook.db.models import RuleSystem, Series
from gamebook.schemas.analysis import FlagUsage, RefOut, WhereUsed
from gamebook.schemas.common import In, Key
from gamebook.schemas.series import (
    RuleSystemCreate,
    RuleSystemOut,
    RuleSystemUpdate,
    SeriesCreate,
    SeriesOut,
    SeriesSummary,
    SeriesUpdate,
)
from gamebook.services import refs, transfer
from gamebook.services import series as svc
from gamebook.services.common import require
from gamebook.services.errors import InvalidError

router = APIRouter(tags=["series"])


@router.get("/series", response_model=list[SeriesSummary])
def list_series(session: SessionDep) -> list[Series]:
    return svc.list_series(session)


@router.post("/series", response_model=SeriesOut, status_code=status.HTTP_201_CREATED)
def create_series(data: SeriesCreate, session: SessionDep) -> Series:
    return svc.create_series(session, data)


@router.get("/series/{series_id}", response_model=SeriesOut)
def get_series(series_id: str, session: SessionDep) -> Series:
    return require(session, Series, series_id)


@router.patch("/series/{series_id}", response_model=SeriesOut)
def update_series(series_id: str, data: SeriesUpdate, session: SessionDep) -> Series:
    return svc.update_series(session, series_id, data)


@router.delete("/series/{series_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_series(series_id: str, session: SessionDep) -> None:
    svc.delete_series(session, series_id)


# ── rule systems ─────────────────────────────────────────────────────────


@router.get("/series/{series_id}/rule-systems", response_model=list[RuleSystemOut])
def list_rule_systems(series_id: str, session: SessionDep) -> list[RuleSystem]:
    return svc.list_rule_systems(session, series_id)


@router.post(
    "/series/{series_id}/rule-systems",
    response_model=RuleSystemOut,
    status_code=status.HTTP_201_CREATED,
)
def create_rule_system(series_id: str, data: RuleSystemCreate, session: SessionDep) -> RuleSystem:
    return svc.create_rule_system(session, series_id, data)


@router.get("/rule-systems/{rule_system_id}", response_model=RuleSystemOut)
def get_rule_system(rule_system_id: str, session: SessionDep) -> RuleSystem:
    return require(session, RuleSystem, rule_system_id)


@router.patch("/rule-systems/{rule_system_id}", response_model=RuleSystemOut)
def update_rule_system(
    rule_system_id: str, data: RuleSystemUpdate, session: SessionDep
) -> RuleSystem:
    return svc.update_rule_system(session, rule_system_id, data)


@router.delete("/rule-systems/{rule_system_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule_system(rule_system_id: str, session: SessionDep) -> None:
    svc.delete_rule_system(session, rule_system_id)


# ── references ───────────────────────────────────────────────────────────

TargetType = Literal[
    "item", "enemy", "table", "character", "lore", "node", "flag", "skill", "class", "stat", "tier"
]


@router.get("/series/{series_id}/where-used", response_model=WhereUsed)
def where_used(
    series_id: str,
    session: SessionDep,
    target_type: TargetType = Query(),
    key: str = Query(),
) -> WhereUsed:
    require(session, Series, series_id)
    rows = refs.where_used(session, series_id, target_type, key)
    out = WhereUsed(
        target_type=target_type,
        target_key=key,
        refs=[
            RefOut(
                source_type=r.source_type,
                source_id=r.source_id,
                book_id=r.book_id,
                node_id=r.node_id,
                node_title=title,
                role=r.role,
                field=r.field,
                qty=r.qty,
            )
            for r, title in rows
        ],
    )
    if target_type == "item":
        countable = {"placement", "shop", "effect.give", "table", "loot"}
        out.total_qty = sum(r.qty or 1 for r, _ in rows if r.role in countable)
    return out


@router.get("/series/{series_id}/flags", response_model=list[FlagUsage])
def list_flags(series_id: str, session: SessionDep) -> list[FlagUsage]:
    require(session, Series, series_id)
    return [
        FlagUsage(flag=f, set_count=c["set"], cleared_count=c["cleared"], tested_count=c["tested"])
        for f, c in refs.flag_usage(session, series_id).items()
    ]


class FlagRename(In):
    old: Key
    new: Key


class RenameResult(In):
    changed: int


@router.post("/series/{series_id}/flags/rename", response_model=RenameResult)
def rename_flag(series_id: str, data: FlagRename, session: SessionDep) -> RenameResult:
    require(session, Series, series_id)
    problem = key_problem(data.new)
    if problem:
        raise InvalidError(problem, field="new")
    return RenameResult(changed=refs.rename_key(session, series_id, "flag", data.old, data.new))


@router.post("/series/{series_id}/reindex", status_code=status.HTTP_204_NO_CONTENT)
def reindex_series(series_id: str, session: SessionDep) -> None:
    """Rebuild the reference index from scratch (maintenance)."""
    require(session, Series, series_id)
    refs.rebuild_series(session, series_id)


# ── export / import ──────────────────────────────────────────────────────


@router.get(
    "/series/{series_id}/export.zip",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}}},
)
def export_series(series_id: str, session: SessionDep) -> Response:
    """Download the series as a git-friendly tree of YAML/Markdown files."""
    filename, data = transfer.export_zip(session, series_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/import",
    response_model=SeriesOut,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def import_series(
    request: Request, session: SessionDep, replace: bool = Query(default=False)
) -> Series:
    """Import a series from an export zip (request body is the zip file)."""
    return transfer.import_zip(session, await request.body(), replace=replace)
