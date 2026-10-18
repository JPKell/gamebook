"""HTTP API (FastAPI). Routers are thin; logic lives in services/ and core/."""

from gamebook.api.app import create_app

__all__ = ["create_app"]
