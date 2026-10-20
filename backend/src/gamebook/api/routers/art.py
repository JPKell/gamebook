"""The asset library, art placements, page setup, maps, appendices and the shot list."""

from typing import Any, Literal

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from gamebook.api.deps import DatabaseDep, SessionDep, SettingsDep
from gamebook.config import Settings
from gamebook.core.art import PageSetup
from gamebook.core.layout import DEFAULT_STYLES, ROLES
from gamebook.db.models import Asset, Map, Series
from gamebook.schemas.art import (
    AppendixIn,
    AppendixOut,
    AppendixUpdate,
    ArtPlacementIn,
    ArtPlacementOut,
    ArtPlacementUpdate,
    AssetOut,
    AssetUpdate,
    AssetUploadOut,
    AssetUse,
    CodexIn,
    MapIn,
    MapOut,
    MapUpdate,
    PageSetupOut,
    RenderOut,
    RoleOut,
    ShotRow,
)
from gamebook.schemas.common import Out, Reorder
from gamebook.services import appendix, art, assets
from gamebook.services.common import require
from gamebook.services.errors import InvalidError

router = APIRouter(tags=["art"])


def _store(settings: Settings) -> assets.Store:
    return assets.Store(settings.data_dir / "assets")


# ── assets ────────────────────────────────────────────────────────────────


@router.get("/series/{series_id}/assets", response_model=list[AssetOut])
def list_assets(series_id: str, session: SessionDep) -> list[Any]:
    counts = assets.use_counts(session, series_id)
    return [
        assets.asset_out(a, counts.get(a.id, 0)) for a in assets.list_assets(session, series_id)
    ]


async def _read_body(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > assets.MAX_BYTES:
        raise InvalidError(f"Images are limited to {assets.MAX_BYTES // (1024 * 1024)} MB")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > assets.MAX_BYTES:
            raise InvalidError(f"Images are limited to {assets.MAX_BYTES // (1024 * 1024)} MB")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/series/{series_id}/assets",
    response_model=AssetUploadOut,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "image/png": {"schema": {"type": "string", "format": "binary"}},
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
                "image/webp": {"schema": {"type": "string", "format": "binary"}},
            },
        }
    },
)
async def upload_asset(
    series_id: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    response: Response,
    filename: str = Query(default="image", max_length=255),
) -> Any:
    """Upload an image as the raw request body. The same image twice returns the existing
    asset (200)."""
    data = await _read_body(request)
    asset, created = await run_in_threadpool(
        assets.upload, session, _store(settings), series_id, filename, data
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return {**assets.asset_out(asset), "created": created}


@router.get("/assets/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: str, session: SessionDep) -> Any:
    a = require(session, Asset, asset_id)
    return assets.asset_out(a, assets.use_counts(session, a.series_id).get(a.id, 0))


@router.patch("/assets/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: str, data: AssetUpdate, session: SessionDep) -> Any:
    a = assets.update(session, asset_id, data)
    return assets.asset_out(a, assets.use_counts(session, a.series_id).get(a.id, 0))


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: str,
    session: SessionDep,
    db: DatabaseDep,
    settings: SettingsDep,
    force: bool = Query(default=False),
) -> Response:
    assets.delete(session, db, _store(settings), asset_id, force=force)
    session.commit()  # GC must see the row gone
    assets.collect_quietly(session, db, _store(settings))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/assets/{asset_id}/where-used", response_model=list[AssetUse])
def asset_where_used(asset_id: str, session: SessionDep) -> list[AssetUse]:
    return assets.where_used(session, asset_id)


def _file(session: Any, settings: Settings, asset_id: str, thumb: bool) -> FileResponse:
    path, mime = assets.file_for(session, _store(settings), asset_id, thumb=thumb)
    if not path.exists():
        raise InvalidError("The image file is missing from the asset store")
    # Content-addressed: the bytes behind a URL never change for a given asset.
    return FileResponse(
        path,
        media_type=mime,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/assets/{asset_id}/file", response_class=FileResponse)
def asset_file(asset_id: str, session: SessionDep, settings: SettingsDep) -> FileResponse:
    return _file(session, settings, asset_id, thumb=False)


@router.get("/assets/{asset_id}/thumb", response_class=FileResponse)
def asset_thumb(asset_id: str, session: SessionDep, settings: SettingsDep) -> FileResponse:
    return _file(session, settings, asset_id, thumb=True)


class GcOut(Out):
    removed: int


@router.post("/assets/gc", response_model=GcOut)
def collect_asset_garbage(session: SessionDep, db: DatabaseDep, settings: SettingsDep) -> GcOut:
    """Remove image files no asset (live or in a checkpoint) refers to."""
    return GcOut(removed=assets.collect_garbage(session, db, _store(settings)))


# ── placements ────────────────────────────────────────────────────────────


@router.get("/placements", response_model=list[ArtPlacementOut])
def list_placements(
    session: SessionDep,
    series_id: str | None = None,
    book_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
) -> list[Any]:
    if not (series_id or book_id or target_id):
        raise InvalidError("Filter by series_id, book_id or target")
    if target_id and not target_type:
        raise InvalidError("target_id needs target_type", field="target_type")
    if target_type and target_type not in art.TARGET_MODELS:
        raise InvalidError(f"Unknown target type {target_type!r}", field="target_type")
    return art.list_placements(
        session,
        series_id=series_id,
        book_id=book_id,
        target_type=target_type,
        target_id=target_id,
    )


@router.post("/placements", response_model=ArtPlacementOut, status_code=status.HTTP_201_CREATED)
def create_placement(data: ArtPlacementIn, session: SessionDep) -> Any:
    return art.placement_out(session, art.create_placement(session, data))


@router.patch("/placements/{placement_id}", response_model=ArtPlacementOut)
def update_placement(placement_id: str, data: ArtPlacementUpdate, session: SessionDep) -> Any:
    return art.placement_out(session, art.update_placement(session, placement_id, data))


@router.delete("/placements/{placement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_placement(placement_id: str, session: SessionDep) -> Response:
    art.delete_placement(session, placement_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/placements/reorder", response_model=list[ArtPlacementOut])
def reorder_placements(data: Reorder, session: SessionDep) -> list[Any]:
    return [art.placement_out(session, p) for p in art.reorder_placements(session, data.ids)]


@router.get("/series/{series_id}/shot-list", response_model=list[ShotRow])
def shot_list(
    series_id: str,
    session: SessionDep,
    status_: str | None = Query(default=None, alias="status"),
    book_id: str | None = None,
    format_: Literal["json", "csv", "md"] = Query(default="json", alias="format"),
) -> Any:
    """Every placement with its brief, status and printed size; CSV or Markdown for
    illustrators."""
    rows = art.shot_list(session, series_id, status=status_, book_id=book_id)
    if format_ == "json":
        return rows
    series = require(session, Series, series_id)
    if format_ == "csv":
        body, media, ext = art.shot_list_csv(rows), "text/csv", "csv"
    else:
        body, media, ext = art.shot_list_markdown(series.title, rows), "text/markdown", "md"
    return Response(
        body,
        media_type=f"{media}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{series.key}-shot-list.{ext}"'},
    )


# ── page setup ────────────────────────────────────────────────────────────


def _setup_out(p: PageSetup) -> PageSetupOut:
    return PageSetupOut(
        **p.model_dump(),
        text_width=round(p.text_width_mm, 1),
        text_height=round(p.text_height_mm, 1),
        roles=[
            RoleOut(key=k, label=label, description=d, default=DEFAULT_STYLES[k])
            for k, (label, d) in ROLES.items()
        ],
    )


@router.get("/books/{book_id}/page-setup", response_model=PageSetupOut)
def get_page_setup(book_id: str, session: SessionDep) -> PageSetupOut:
    return _setup_out(art.get_page_setup(session, book_id))


@router.put("/books/{book_id}/page-setup", response_model=PageSetupOut)
def save_page_setup(book_id: str, data: PageSetup, session: SessionDep) -> PageSetupOut:
    return _setup_out(art.save_page_setup(session, book_id, data))


# ── maps ──────────────────────────────────────────────────────────────────


@router.get("/series/{series_id}/maps", response_model=list[MapOut])
def list_maps(series_id: str, session: SessionDep, book_id: str | None = None) -> list[Any]:
    return [art.map_out(session, m) for m in art.list_maps(session, series_id, book_id)]


@router.post("/series/{series_id}/maps", response_model=MapOut, status_code=status.HTTP_201_CREATED)
def create_map(series_id: str, data: MapIn, session: SessionDep) -> Any:
    return art.map_out(session, art.create_map(session, series_id, data))


@router.get("/maps/{map_id}", response_model=MapOut)
def get_map(map_id: str, session: SessionDep) -> Any:
    return art.map_out(session, require(session, Map, map_id))


@router.patch("/maps/{map_id}", response_model=MapOut)
def update_map(map_id: str, data: MapUpdate, session: SessionDep) -> Any:
    return art.map_out(session, art.update_map(session, map_id, data))


@router.delete("/maps/{map_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_map(map_id: str, session: SessionDep) -> Response:
    art.delete_map(session, map_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── appendices ────────────────────────────────────────────────────────────


@router.get("/books/{book_id}/appendices", response_model=list[AppendixOut])
def list_appendices(book_id: str, session: SessionDep) -> list[Any]:
    return appendix.list_appendices(session, book_id)


@router.post(
    "/books/{book_id}/appendices", response_model=AppendixOut, status_code=status.HTTP_201_CREATED
)
def create_appendix(book_id: str, data: AppendixIn, session: SessionDep) -> Any:
    return appendix.create(session, book_id, data)


@router.post("/books/{book_id}/appendices/reorder", response_model=list[AppendixOut])
def reorder_appendices(book_id: str, data: Reorder, session: SessionDep) -> list[Any]:
    return appendix.reorder(session, book_id, data.ids)


@router.patch("/appendices/{appendix_id}", response_model=AppendixOut)
def update_appendix(appendix_id: str, data: AppendixUpdate, session: SessionDep) -> Any:
    return appendix.update(session, appendix_id, data)


@router.delete("/appendices/{appendix_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appendix(appendix_id: str, session: SessionDep) -> Response:
    appendix.delete(session, appendix_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class RenderedOut(RenderOut):
    #: A standalone page (styles inlined) for an iframe preview.
    document: str


@router.get("/appendices/{appendix_id}/render", response_model=RenderedOut)
def render_appendix(appendix_id: str, session: SessionDep) -> RenderedOut:
    title, fragment, doc = appendix.render_document(session, appendix_id)
    return RenderedOut(title=title, html=fragment, document=doc)


class CodexEntry(Out):
    id: str
    title: str
    document: str


@router.post("/books/{book_id}/codex", response_model=list[CodexEntry])
def book_codex(book_id: str, data: CodexIn, session: SessionDep) -> list[CodexEntry]:
    """The player's codex: enabled appendices, with bestiary and items limited to what the
    reader has met."""
    return [
        CodexEntry(id=i, title=t, document=d) for i, t, d in appendix.codex(session, book_id, data)
    ]
