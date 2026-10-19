"""Print editions: preflight, proof, numbering, verification and PDF/EPUB exports."""

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, HTMLResponse

from gamebook.api.deps import SessionDep, SettingsDep
from gamebook.schemas.playtest import JobOut
from gamebook.schemas.printing import (
    ExportIn,
    PreflightOut,
    ReshuffleIn,
    ReshuffleOut,
    VerifyIn,
    VerifyOut,
)
from gamebook.services import playtest, printing
from gamebook.services.assets import Store

router = APIRouter(tags=["print"])


@router.get("/books/{book_id}/print/preflight", response_model=PreflightOut)
def print_preflight(book_id: str, session: SessionDep, tier: str | None = None) -> PreflightOut:
    """Section count, numbering, print warnings and art problems for one tier's edition."""
    return PreflightOut.model_validate(printing.preflight(session, book_id, tier))


@router.get("/books/{book_id}/print/preview", response_class=HTMLResponse)
def print_preview(book_id: str, session: SessionDep, tier: str | None = None) -> HTMLResponse:
    """The proof: the whole edition as one HTML page (for an iframe)."""
    return HTMLResponse(
        printing.preview_html(session, book_id, tier),
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
