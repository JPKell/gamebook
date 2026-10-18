# v2 Phase 0 — Foundations

**Status:** Complete · **Date:** 2026-10-17 · **Branch:** `v2`

## What was built

### Repository
- v1 tagged `v1-prototype` and removed; v1 spec/plan in `docs/archive/`, v1 handoffs in `docs/handoffs/v1/`.
- New layout: `backend/` (uv, src layout), `frontend/` (Vite), `docs/` (SPEC, PLAN, ADRs, handoffs).
- Root `Makefile` (`make help`), `.pre-commit-config.yaml` (local hooks), GitHub Actions CI (`.github/workflows/ci.yml`).

### Backend (`backend/src/gamebook/`)
| Module | Purpose |
|---|---|
| `config.py` | `Settings` (pydantic-settings): init → `GAMEBOOK_*` env → `.env` → `config.yaml` (or `$GAMEBOOK_CONFIG`) → defaults. `database_url` defaults to `<data_dir>/gamebook.db`. |
| `logging_setup.py` | Text or JSON log lines with `extra=` fields; uvicorn routed through it. |
| `ids.py` | Monotonic UUIDv7 (`uuid7()`, `new_id()`); works on 3.12 (no stdlib `uuid7` dependency). |
| `db/base.py` | `Base` with constraint naming convention, `IdMixin`, `TimestampMixin`. |
| `db/session.py` | `make_engine` (SQLite: creates dir, WAL, FK on, busy timeout), `Database` with `session()` unit of work and `ping()`. |
| `db/repository.py` | Generic `Repository[Model]` (`get/require/list/count/add/delete`), `NotFoundError`. Repos flush, never commit. |
| `db/migrate.py` + `db/migrations/` | In-package Alembic (batch mode for SQLite); baseline revision `0001` is empty. |
| `db/models.py` | Model registry — **import every new model module here** so Alembic and tests see it. |
| `api/app.py` | `create_app(settings, database=)`: auto-migrate on startup, CORS, error handlers, operation ids = function names, optional SPA serving via 404-fallback middleware. |
| `api/errors.py` | Uniform error envelope `{detail, code}` (+ `errors` on 422); `NotFoundError` → 404; unhandled → 500 without leaking. |
| `api/deps.py` | `SessionDep` (request-scoped unit of work), `DatabaseDep`, `SettingsDep`. |
| `api/routers/health.py` | `GET /api/health` → `{status, version, database}`. |
| `cli.py` | `gamebook serve [--reload]`, `gamebook db upgrade|revision -m`, `gamebook openapi -o file`. |
| `core/`, `services/`, `llm/`, `export/`, `jobs/` | Empty packages with layering docstrings. |

### Frontend (`frontend/src/`)
- **Shell:** nav rail (9 sections from `app/sections.ts`, the single registry for nav, routes and palette), top bar (breadcrumb stub, command search button, global **rules tier** selector, theme cycle), status bar with Problems panel stub (Ctrl/⌘+J) and live backend status, skip link.
- **Command palette** (Ctrl/⌘+K, cmdk): go-to sections, set tier, theme, toggle problems.
- **State:** TanStack Query for server data (`api/queries.ts`); Zustand `stores/ui.ts` for UI prefs (theme/tier/panel persisted via a localStorage wrapper that tolerates blocked storage).
- **API client:** `api/client.ts` — `openapi-fetch` over generated `api/schema.d.ts`; `unwrap()` throws `ApiError {status, code}` from the backend envelope.
- **Design tokens:** `index.css` semantic colors (`bg`, `surface`, `surface-2`, `border`, `text`, `muted`, `accent`, `danger`, `warning`, `info`, `success`) in light and dark; use these, never raw palette colors.
- Section pages are placeholders (`features/placeholder/`) listing what arrives in which phase.

### Tests (all green)
- Backend 24: health, auto-migration, operation ids, error envelopes, SPA serving incl. traversal and 404/405 semantics, settings precedence, UUIDv7 ordering, SQLite pragmas, repository + unit of work, migrations idempotent, **models ↔ migrations drift check**, **architecture rules** (core purity; routers don't import llm/export/jobs), CLI openapi.
- Frontend 14 (Vitest): routing/redirect, nav, backend status (up/down), tier selector, problems toggle, theme, palette (Ctrl+K, search button, Escape), API error unwrapping.
- E2E 3 (Playwright, built UI served by the real API on :8765 with a throwaway data dir).
- Verified on Python 3.12 and 3.14.

## Decisions made during the phase
- **Migrations live inside the package** and run on startup (`auto_migrate`, default on). No `alembic.ini`; use `gamebook db ...`.
- **React 19 / TS 6 / Vite 8 / Tailwind 4** (current stable; SPEC updated). `openapi-typescript` peers TS 5 → npm `overrides` (ADR 0001).
- **oxlint** instead of ESLint (shipped by the Vite template, much faster).
- **`httpx2`** for the test client (Starlette deprecation of `httpx`).
- SPA is served via a 404-fallback middleware, not a catch-all route, so unknown `POST /api/...` is 404 and wrong-method is 405.
- The rules-tier selector is global UI state now; Phase 3 will make it drive the mechanics editor, enemy stats and the player.

## Known issues / notes
- Frontend bundle is ~490 kB (157 kB gzip) in one chunk; add route-level `lazy()` code-splitting when real sections land (Phase 2).
- The breadcrumb is static ("No series open") until Phase 2 adds series/book switching.
- `pre-commit install` was not run (it modifies `.git/hooks`); run `cd backend && uv run pre-commit install` if wanted.
- CI workflow has not run yet (nothing pushed).

## Phase 1 starting points
1. **gbx** in `core/gbx/` (lexer → Pratt parser → AST JSON → checker → evaluator with injected RNG → printer). Hypothesis: parse(print(ast)) == ast; evaluator total on well-typed input.
2. Domain models per SPEC §2 in `db/` (one module per aggregate), registered in `db/models.py`; generate migration `0002` with `gamebook db revision -m "domain model"` and review it.
3. Pydantic schemas in `api/schemas/`; services in `services/`; routers stay thin. Re-run `make gen-api` after schema changes (CI enforces freshness).
4. RefIndex maintained in the service layer on every write.
5. Validation v1 (`core/analysis/validation.py`) + `GET /api/books/{id}/problems`; wire the Problems panel counts.
6. Git tree export/import with a round-trip test.
