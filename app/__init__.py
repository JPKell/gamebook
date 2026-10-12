"""
FastAPI application factory for the Gamebook Authoring Tool.

This module creates the FastAPI application instance, configures lifespan
events (database engine initialization, migration checks), registers all
router modules, and sets up middleware (CORS, request logging).

The app itself is stateless — all state lives in the database. This factory
pattern means tests can create an app instance without running the server.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import series, books, book_detail, acts, nodes, locations, items, encounters


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events for the application.

    On startup: verify the database engine is connected and all tables
    exist (or are created via SQLAlchemy metadata). On shutdown: dispose
    the engine pool.
    """
    # TODO: Add engine connection check on startup.
    yield
    # Engine disposal handled by SQLAlchemy session management.


def create_app() -> FastAPI:
    """
    Application factory.

    Creates and configures the FastAPI app with middleware, routers,
    static file serving, and lifespan events. Called once at server
    startup (e.g. by uvicorn) and by tests.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="Gamebook Authoring Tool",
        description=(
            "Visual authoring tool for interactive gamebooks organized into "
            "series and books. Graph-based story editor with AI-assisted "
            "story generation, playthrough evaluation, and assembly output."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow the frontend origin during development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register route modules.
    app.include_router(series.router, prefix="/api/series", tags=["series"])
    app.include_router(books.router, prefix="/api/series", tags=["books"])
    app.include_router(book_detail.router, prefix="/api/books", tags=["book-detail"])
    app.include_router(acts.router, prefix="/api/books", tags=["acts"])
    app.include_router(nodes.router, prefix="/api/books", tags=["nodes"])
    app.include_router(
        locations.router, prefix="/api", tags=["locations"]
    )
    app.include_router(items.router, prefix="/api", tags=["items"])
    app.include_router(
        encounters.router, prefix="/api", tags=["encounters"]
    )

    # Serve static frontend files.
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    return app
