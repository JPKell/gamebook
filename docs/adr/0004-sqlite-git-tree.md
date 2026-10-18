# ADR 0004 — SQLite as working store, git tree as durable format

**Status:** Accepted (2026-10-17)

## Context
Single local user. Needs rich queries (where-used, reachability, playtest
analytics) and also history/diff/backup of the writing.

## Decision
SQLite (WAL, foreign keys on) is the live store; Alembic migrations ship inside
the package and run automatically at startup. A deterministic export to a
directory of YAML/Markdown files (one per node/enemy/item/lore entry) round-trips
back into the DB and is what the author commits to git. Primary keys are UUIDv7;
every entity also has a human `key` used in expressions and exports.

## Consequences
No server database to run. Export/import must stay lossless — a round-trip test is
part of CI from Phase 1. PostgreSQL remains possible via SQLAlchemy if ever needed.
