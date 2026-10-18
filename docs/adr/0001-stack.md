# ADR 0001 — Technology stack

**Status:** Accepted (2026-10-17)

## Context
Single author, running locally; the tool must grow to a large UI (graph editor,
entity managers, dashboards) and a Python-heavy backend (rules engine, simulation,
LLM orchestration, PDF/EPUB). v1 used vanilla JS in a single 1,400-line file,
which did not scale.

## Decision
- **Backend:** Python ≥3.12, uv, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic.
- **Frontend:** Vite, React 19, TypeScript (strict), React Flow for the graph,
  TanStack Query (server state), Zustand (UI state), Tailwind v4 with semantic
  design tokens, Radix primitives, cmdk.
- **Contract:** OpenAPI is the source of truth; TS types are generated
  (`openapi-typescript` + `openapi-fetch`) and CI fails if they are stale.
- **Quality:** ruff, mypy (strict on `core/`), pytest + Hypothesis; oxlint,
  prettier, Vitest + Testing Library; Playwright e2e against the real API.

## Consequences
A build step and two toolchains, offset by type safety end-to-end and the
largest component ecosystem. `openapi-typescript` declares a TS 5 peer; an npm
`overrides` entry points it at the project's TS 6 (it is a build-time tool only).
