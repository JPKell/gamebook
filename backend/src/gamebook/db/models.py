"""Model registry.

Import every ORM model module here so ``Base.metadata`` is complete for
Alembic autogenerate and ``create_all`` in tests. Domain tables arrive in Phase 1.
"""

from gamebook.db.base import Base

__all__ = ["Base"]
