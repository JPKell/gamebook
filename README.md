# Gamebook Studio

A local authoring studio for choose-your-own-adventure RPG gamebooks: series →
books → acts → nodes, layered Basic/Medium/Advanced rules, enemies and items,
lore, LLM-assisted prose, bot and LLM playtesting, and print/EPUB/digital output.

- **Spec:** [`docs/SPEC.md`](docs/SPEC.md) · **Plan:** [`docs/PLAN.md`](docs/PLAN.md)
- **Decisions:** [`docs/adr/`](docs/adr) · **Phase handoffs:** [`docs/handoffs/`](docs/handoffs)

## Requirements

- Python ≥ 3.12 with [uv](https://docs.astral.sh/uv/)
- Node ≥ 20.19 (24 LTS recommended)

## Quick start

```bash
make install     # uv sync + npm ci
make dev         # API on :8789 (auto-reload) + UI on http://localhost:5173
```

The database is created and migrated automatically in `backend/data/gamebook.db`
on first start. Copy `backend/config.example.yaml` to `backend/config.yaml` to change
settings, or use `GAMEBOOK_*` environment variables.

`make serve` builds the UI and serves everything from the API on http://localhost:8788.

### Running as a service

`deploy/gamebook.service` is a systemd user unit serving the built app on
**:8788** (all interfaces). `make install-service` installs it; `make deploy`
rebuilds the UI and restarts it. It runs whatever is checked out, and shares
`backend/data/` with `make dev` (which uses :8789 so both can run).

## Development

| Command | What it does |
|---|---|
| `make check` | Everything CI runs: lint, typecheck, tests, e2e |
| `make test` | pytest + vitest |
| `make e2e` | Playwright against the built UI + real API |
| `make gen-api` | Regenerate TS types after changing API schemas |
| `make format` | ruff + prettier |

Optional git hooks: `cd backend && uv run pre-commit install`.

### Layout

```
backend/src/gamebook/
  core/      pure, deterministic domain logic (rules language, engine, analysis)
  db/        SQLAlchemy models, repositories, in-package Alembic migrations
  api/       FastAPI app + thin routers
  services/  use-cases;  llm/  export/  jobs/  (later phases)
frontend/src/
  app/       shell, routing, command palette
  features/  one folder per section
  api/       generated OpenAPI client
```

`gamebook --help` lists backend CLI commands:

| Command | |
|---|---|
| `gamebook serve [--reload] [--port N]` | Run the API (default :8788) |
| `gamebook export <series-key> <dir>` | Write a series as a git-friendly YAML/Markdown tree |
| `gamebook import <dir> [--replace]` | Load a series from such a tree |
| `gamebook db upgrade/downgrade/revision` | Migrations (applied automatically on start) |
| `gamebook openapi -o file` | Dump the OpenAPI schema |

The API is browsable at http://localhost:8788/docs.

The v1 prototype is preserved at the `v1-prototype` git tag.
