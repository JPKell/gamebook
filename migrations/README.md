"""
Alembic migration configuration.

Manages database schema migrations for the Gamebook Authoring Tool.
Initial migration creates all tables based on SQLAlchemy model metadata.

Usage:
  cd ~/repos/gamebook
  alembic upgrade head    # Apply all pending migrations
  alembic revision --autogenerate -m "add_playthrough"  # Generate new migration
  alembic downgrade -1    # Roll back one migration
"""
