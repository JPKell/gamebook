# Gamebook Authoring Tool — Phase Handoff

## What Was Done (Phase 1: Project Scaffold & Data Model)

### Completed
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

---

## What's Next

### Phase 2: Graph Canvas (Core UX)
**Goal:** Interactive node graph on Canvas API — drag nodes, draw connections, edit content.

**To implement:**
1. **Canvas rendering** — replace placeholder with Canvas API drawing of nodes as rounded rectangles with title text, color-coded by type (green=entry, default=beat, orange=exit, red=ending).
2. **Pan & zoom** — middle-click drag or space+drag for pan, scroll wheel for zoom.
3. **Connections** — bezier curves with arrows between nodes via Choice relationships.
4. **Drag nodes** — reposition on canvas, save x/y to database on drag end (debounced API call).
5. **Connect Forward / Connect Back** — right-click node → modal with choice text input + searchable node dropdown (same book) → creates Choice → redraws connections.
6. **Node Edit modal** — double-click node → edit title, description (textarea), type, location (shared+book dropdown), act, items, encounters → PUT to API.
7. **Act highlighting** — toolbar "Select Act" highlights nodes in that act with colored border.
8. **Book switching** — clicking different book in sidebar clears canvas, loads new graph.

**Key files to modify:**
- `app/static/index.html` — add canvas element, modals
- `app/static/js/app.js` — canvas rendering, pan/zoom, drag, connection drawing, modal handlers
- `app/static/css/style.css` — canvas container, modal styling
- `app/static/js/main.js` — bootstrapping updates

**API endpoints to call:**
- `GET /api/books/{id}` — loads full graph data
- `PUT /api/books/{id}/nodes/{id}` — save node position
- `POST /api/books/{id}/nodes/{id}/choices` — create connection
- `DELETE /api/books/{id}/choices/{id}` — remove connection

### Phase 3: Act Management
Proper act editor view with entry/exit selectors, validation engine in UI (status bar with errors/warnings).

### Phase 4: Preview Mode
Reader experience — play through the gamebook, track inventory, encounter system.

### Phase 5+: See `plan.md`

---

## Known Issues / Decisions Made During Phase 1

1. **Route collision fixed:** Book-level endpoints (`GET /api/books/{id}`) were initially mounted under `/api/series` creating path conflicts. Split into `books.py` (series-scoped `/{series_id}/books`) and `book_detail.py` (standalone `/{book_id}`).

2. **Python 3.14 compatibility:** Pinned versions in `requirements.txt` replaced with `>=` ranges since Python 3.14 needs newer package versions.

3. **Shared entity pattern:** Locations, Items, Encounters support both series-level and book-level scopes via nullable `series_id` + `book_id` columns. If `series_id` is set → shared; if only `book_id` is set → book-specific.

4. **All Python files have top-level docstrings** explaining what the file holds and why.

5. **No Pydantic schemas yet** — endpoints use raw `dict` for request bodies. Schemas can be added in Phase 2 for stricter validation.
