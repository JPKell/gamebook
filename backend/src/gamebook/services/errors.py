"""Service-level errors, mapped to HTTP responses by the API layer."""

from typing import Any


class ServiceError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ConflictError(ServiceError):
    """The request conflicts with existing data (key taken, entity in use…)."""

    status = 409
    code = "conflict"


class InvalidError(ServiceError):
    """Semantically invalid request (e.g. node and act from different books)."""

    status = 422
    code = "invalid"
