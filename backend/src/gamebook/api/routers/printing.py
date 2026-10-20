"""Print editions: preflight, proof, numbering, verification and PDF/EPUB exports."""

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse

from gamebook.api.deps import SessionDep, SettingsDep
from gamebook.config import Settings
from gamebook.schemas.playtest import JobOut
from gamebook.schemas.printing import (
    ExportIn,
    FontOut,
    FontsOut,
    PreflightOut,
    ReshuffleIn,
    ReshuffleOut,
    VerifyIn,
    VerifyOut,
)
from gamebook.services import fonts, playtest, printing
from gamebook.services.assets import Store
from gamebook.services.errors import InvalidError

router = APIRouter(tags=["print"])


def _fonts(settings: Settings) -> fonts.FontStore:
    return fonts.FontStore(settings.data_dir / "fonts")


@router.get("/books/{book_id}/print/preflight", response_model=PreflightOut)
def print_preflight(book_id: str, session: SessionDep, tier: str | None = None) -> PreflightOut:
    """Section count, numbering, print warnings and art problems for one tier's edition."""
    return PreflightOut.model_validate(printing.preflight(session, book_id, tier))


@router.get("/books/{book_id}/print/preview", response_class=HTMLResponse)
def print_preview(
    book_id: str, session: SessionDep, settings: SettingsDep, tier: str | None = None
) -> HTMLResponse:
    """The proof: the whole edition as one HTML page (for an iframe)."""
    return HTMLResponse(
        printing.preview_html(session, book_id, tier, _fonts(settings)),
        headers={
            "X-Content-Type-Options": "nosniff",
            # Author content can't run scripts here.
            "Content-Security-Policy": (
                "script-src 'none'; object-src 'none'; form-action 'none'; "
                "frame-ancestors 'self'; sandbox"
            ),
        },
    )


@router.post("/books/{book_id}/print/reshuffle", response_model=ReshuffleOut)
def reshuffle_sections(book_id: str, data: ReshuffleIn, session: SessionDep) -> ReshuffleOut:
    """Renumber every section (pinned ones stay). Earlier exports' numbers won't match."""
    return ReshuffleOut(seed=printing.reshuffle(session, book_id, data.seed))


@router.post("/books/{book_id}/print/verify", response_model=VerifyOut)
def verify_print(book_id: str, data: VerifyIn, session: SessionDep) -> VerifyOut:
    """Bots play the engine; every move must have its printed instruction and number."""
    r = printing.verify_book(session, book_id, data.tier, data.runs)
    return VerifyOut(
        ok=r.ok,
        runs=r.runs,
        moves=r.moves,
        arrivals=r.arrivals,
        problems=r.problems,
        samples=r.samples,
        unvisited=r.unvisited,
        structure=r.structure,
    )


@router.post("/books/{book_id}/print/exports", response_model=JobOut, status_code=201)
def start_print_export(
    book_id: str,
    data: ExportIn,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
) -> JobOut:
    """Build the PDF or EPUB in the background; download it when the job is done."""
    job = printing.start_export(session, book_id, data.tier, data.format)
    session.commit()
    runner: playtest.Runner = request.app.state.jobs
    payload = job.payload or {}
    runner.submit(
        job.id,
        printing.export_job(
            book_id,
            payload["tier"],
            data.format,
            Store(settings.data_dir / "assets"),
            printing.exports_dir(settings.data_dir),
            settings.web_player_dist(),
            fonts=_fonts(settings),
            imposed=data.imposed,
        ),
    )
    return JobOut.model_validate(job)


@router.get("/print/exports/{job_id}", response_class=FileResponse)
def download_print_export(
    job_id: str, session: SessionDep, settings: SettingsDep, inline: bool = Query(default=False)
) -> FileResponse:
    path, name, media = printing.export_file(
        session, printing.exports_dir(settings.data_dir), job_id
    )
    return FileResponse(
        path,
        media_type=media,
        filename=name,
        content_disposition_type="inline" if inline else "attachment",
    )


@router.get("/books/{book_id}/print/sample", response_class=Response)
async def print_sample(
    book_id: str,
    session: SessionDep,
    settings: SettingsDep,
    tier: str | None = None,
    imposed: bool = False,
) -> Response:
    """A quick PDF of the front matter and first sections, to check a layout."""
    out = await run_in_threadpool(
        printing.pdf,
        session,
        Store(settings.data_dir / "assets"),
        book_id,
        tier,
        fonts=_fonts(settings),
        imposed=imposed,
        sample=True,
    )
    return Response(
        out.data,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline", "Cache-Control": "no-store"},
    )


# ── fonts ─────────────────────────────────────────────────────────────────


def _font_out(f: fonts.FontFile) -> FontOut:
    return FontOut(
        id=f.id, file=f.file, family=f.family, weight=f.weight, italic=f.italic, bytes=f.bytes
    )


@router.get("/print/fonts", response_model=FontsOut)
def list_fonts(settings: SettingsDep) -> FontsOut:
    """Families a layout can use: installed ones, uploaded files and CSS generics."""
    return FontsOut(
        system=list(fonts.system_families()),
        uploaded=[_font_out(f) for f in _fonts(settings).list()],
        generic=fonts.GENERIC,
    )


@router.post(
    "/print/fonts",
    response_model=FontOut,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload_font(request: Request, settings: SettingsDep) -> FontOut:
    """Upload a TrueType, OpenType or WOFF font as the raw request body."""
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > fonts.MAX_BYTES:
            raise InvalidError("Font files must be at most 15 MB")
        chunks.append(chunk)
    f = await run_in_threadpool(_fonts(settings).add, b"".join(chunks))
    return _font_out(f)


@router.delete("/print/fonts/{font_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_font(font_id: str, settings: SettingsDep) -> Response:
    """Remove an uploaded font (layouts using it fall back to the default font)."""
    _fonts(settings).delete(font_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/print/fonts/{name}", response_class=FileResponse)
def font_file(name: str, settings: SettingsDep) -> FileResponse:
    path = _fonts(settings).path(name)
    if not path.is_file():
        raise fonts.NotFoundError("No such font")
    return FileResponse(
        path,
        media_type=fonts.MIMES[path.suffix[1:]],
        # The proof is a sandboxed (opaque-origin) frame: fonts need CORS there.
        headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "max-age=31536000"},
    )
