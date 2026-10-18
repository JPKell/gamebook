"""Error envelope and exception handlers.

Every error response is ``{"detail": str, "code": str}`` (plus ``errors`` for
request validation failures and ``details`` for service errors) so the frontend
can handle them uniformly.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from gamebook.db.repository import NotFoundError
from gamebook.services.errors import ServiceError

log = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    detail: str
    code: str
    details: dict[str, object] | None = None


def _error(status: int, detail: str, code: str, **extra: object) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail, "code": code, **extra})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return _error(404, str(exc), "not_found")

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError) -> JSONResponse:
        extra = {"details": exc.details} if exc.details else {}
        return _error(exc.status, exc.message, exc.code, **extra)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else f"http_{exc.status_code}"
        return _error(exc.status_code, str(exc.detail), code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # jsonable_encoder: errors from model validators carry exception objects in ctx.
        errors = jsonable_encoder(exc.errors())
        return _error(422, "Request validation failed", "validation_error", errors=errors)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error", extra={"path": request.url.path})
        return _error(500, "Internal server error", "internal_error")
