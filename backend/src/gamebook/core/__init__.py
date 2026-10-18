"""Pure domain layer.

Everything under ``gamebook.core`` is deterministic, typed and free of IO:
no database, no HTTP, no filesystem, no LLM calls. The rest of the application
depends on ``core``; ``core`` depends on nothing else in the app. This is
enforced by ``tests/test_architecture.py``.
"""
