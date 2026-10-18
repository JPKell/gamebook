# ADR 0002 — Pure, deterministic core

**Status:** Accepted (2026-10-17)

## Context
The same rules must drive the in-app player, rule-based bots, LLM players,
validation, the state-digest analysis and print rendering, and later be ported to
TypeScript for the standalone player.

## Decision
`gamebook.core` contains all rules/engine/analysis logic and may import only the
standard library (no IO modules), itself, and `pydantic`. Randomness comes from an
explicitly seeded RNG passed in; every roll is an event. Other packages depend on
`core`, never the reverse. `tests/test_architecture.py` enforces this, and also keeps
API routers from importing `llm/`, `export/` or `jobs/` directly (they go via `services/`).

## Consequences
Engine code is trivially testable and replayable (golden traces). Persistence
mapping lives in `db/`/`services/`, which costs some translation code.
