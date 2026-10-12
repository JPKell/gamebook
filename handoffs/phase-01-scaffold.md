# Phase 1 — Project Scaffold & Data Model

## What Was Done

1. **FastAPI app factory** (`app/__init__.py`) — creates the app with lifespan events, CORS middleware, static file serving, and registers all API routers.
2. **Configuration** (`app/config.py`, `config.example.yaml`) — loads settings from `config.yaml` with env var override. Supports SQLite (dev) and PostgreSQL (prod).
3. **Database** (`app/database.py`) — SQLAlchemy engine, session factory, `Base` class.
4. **8 ORM models** in `app/models/`:
   - `Series` — top-level world container with tone, worldGuidelines, relationships to Books and shared entities.
   - `Book` — story graph owned by a Series, with acts list and node count.
   - `Act` — chapter within a book, tracks entry/exit node sets and node membership.
   - `Node` — individual story beats with position (x,y), type (entry/beat/exit/ending), location, items, encounters, and story generation fields (`storyText`, `storyStatus`, `storyModel`, `storyPrompt`).
   - `Choice` — links two nodes (source→target) with text, enforces same-book constraint.
   - `Location`, `Item`, `Encounter` — each with `seriesId` + `bookId` columns for shared vs. book-specific scoping.
5. **17 API routes** in `app/routes/`:
   - Series CRUD + JSON export
   - Book listing/creation (scoped to series)
   - Book detail (standalone get/update/delete with full nested data)
   - Acts CRUD + node assignment
   - Nodes CRUD + choices, items, encounters
   - Locations, Items, Encounters (series-level shared + book-level specific endpoints)
6. **Services**:
   - `inference.py` — HTTP client to external inference endpoint with retries, backoff, error handling.
   - `validation.py` — graph validation: act continuity, missing node references, cross-book choice enforcement, ending constraints.
7. **Static frontend shell**: HTML SPA structure with sidebar, canvas container, modals, dark theme CSS, vanilla JS app skeleton.
8. **Integration tests** (`tests/test_api.py`) — 8 tests covering full CRUD flow: create series → create book → get book with entities → create node → create choice → verify cross-book choice fails → create shared location → delete series cascades. **All 8 pass.**
9. **Alembic migration guide**, `requirements.txt`, `.gitignore`, `README.md` with API reference.

### Git
- `git commit` on `master` — no push. Clean tree (35 files, no pycache/db artifacts).

### Files created
- `app/__init__.py`, `app/config.py`, `app/database.py`
- `app/models/{series,book,act,node,choice,location,item,encounter}.py`
- `app/routes/{series,books,book_detail,acts,nodes,locations,items,encounters}.py`
- `app/services/{inference,validation}.py`
- `app/static/{index.html,js/app.js,js/main.js,css/style.css}`
- `migrations/README.md`
- `tests/{__init__,test_api}.py`
- `requirements.txt`, `config.example.yaml`, `README.md`, `.gitignore`, `spec.md`, `plan.md`

## Known Issues / Decisions Made

1. **Route collision fixed:** Book-level endpoints (`GET /api/books/{id}`) were initially mounted under `/api/series` creating path conflicts. Split into `books.py` (series-scoped `/{series_id}/books`) and `book_detail.py` (standalone `/{book_id}`).

2. **Python 3.14 compatibility:** Pinned versions in `requirements.txt` replaced with `>=` ranges since Python 3.14 needs newer package versions.

3. **Shared entity pattern:** Locations, Items, Encounters support both series-level and book-level scopes via nullable `series_id` + `book_id` columns. If `series_id` is set → shared; if only `book_id` is set → book-specific.

4. **All Python files have top-level docstrings** explaining what the file holds and why.

5. **No Pydantic schemas yet** — endpoints use raw `dict` for request bodies. Schemas can be added in Phase 2 for stricter validation.
