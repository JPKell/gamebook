"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from gamebook import __version__
from gamebook.api.errors import ErrorResponse, install_error_handlers
from gamebook.api.routers import books, entities, health, history, nodes, series, tools
from gamebook.config import Settings, get_settings
from gamebook.db import migrate
from gamebook.db.session import Database
from gamebook.logging_setup import configure_logging

log = logging.getLogger(__name__)

API_PREFIX = "/api"


def _operation_id(route: APIRoute) -> str:
    # Stable, readable operation ids (= Python function names) for the
    # generated TypeScript client.
    return route.name


def create_app(settings: Settings | None = None, *, database: Database | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        if settings.auto_migrate and database is None:
            migrate.upgrade(settings.database_url)
        app.state.db = database or Database(settings.database_url)
        log.info("Gamebook Studio started", extra={"version": __version__})
        try:
            yield
        finally:
            if database is None:
                app.state.db.dispose()

    app = FastAPI(
        title="Gamebook Studio",
        version=__version__,
        lifespan=lifespan,
        generate_unique_id_function=_operation_id,
        responses={500: {"model": ErrorResponse}},
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    for module in (health, series, books, nodes, entities, history, tools):
        app.include_router(module.router, prefix=API_PREFIX)

    if settings.frontend_dist is not None:
        _mount_frontend(app, settings.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built SPA.

    Implemented as a 404 fallback rather than a catch-all route so API method
    semantics stay intact (e.g. POST to an unknown /api path is 404, not 405).
    """
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        log.warning("frontend_dist has no index.html; not serving UI", extra={"dist": str(dist)})
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.middleware("http")
    async def spa_fallback(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        path = request.url.path
        if (
            response.status_code != 404
            or request.method not in ("GET", "HEAD")
            or path == API_PREFIX
            or path.startswith(API_PREFIX + "/")
        ):
            return response
        candidate = (dist / path.lstrip("/")).resolve()
        if candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate)
        return FileResponse(index)
