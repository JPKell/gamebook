# Phase 2 — Graph Canvas (Core UX)

## What Was Done

1. **Canvas rendering** — nodes drawn as rounded rectangles, color-coded by type (green=entry, default=beat, orange=exit, red=ending). Type indicator dots in top-left corner. Selection glow effect.
2. **Pan & zoom** — middle-click drag or space+drag for pan, scroll wheel for zoom (anchored to mouse position, not center). 0.2x–3x range.
3. **Connections** — bezier curves with arrowheads at node edges (not centers). Arrow tangent-aligned to curve.
4. **Drag nodes** — click and drag to reposition on canvas. Debounced position save to API (300ms). Undo recorded.
5. **Connect Forward / Connect Back** — right-click node opens modal with choice text input + destination dropdown → creates Choice via API.
6. **Node Edit modal** — double-click node → edit title, description (textarea), type, location, act, items, encounters → PUT to API. Delete button included.
7. **Act highlighting** — clicking an act in the sidebar toggles colored halo around nodes in that act.
8. **Book switching** — selecting a different book in the sidebar clears canvas, loads new graph with fresh undo stack.
9. **Undo system** — `Ctrl+Z` for undo create/delete/move node and choices. 20-step undo stack. Button in toolbar.
10. **Keyboard shortcuts** — Delete to remove selected node, Escape to close modals/deselect, Ctrl+Z for undo, Space for pan mode.
11. **Zoom indicator** — percentage shown in bottom-right corner of canvas.
12. **Status bar** — updates on every action (load, create, delete, move, undo).
13. **Button state management** — Validate/Save enabled after loading a series or book.

### Git
- `git commit` on `master` — no push.

### Files modified
- `app/static/js/app.js` — full rewrite of canvas logic (~1140 lines)
- `app/static/index.html` — added Undo button to toolbar
- `app/static/css/style.css` — canvas cursor states, status bar visibility

### Files created
- `handoffs/phase-01-scaffold.md` — Phase 1 handoff document

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /api/series/` | Load series list |
| `GET /api/series/{id}` | Load single series |
| `POST /api/series/` | Create series |
| `GET /api/books/{id}` | Load book with full graph |
| `POST /api/series/{id}/books` | Create book |
| `PUT /api/books/{id}/nodes/{id}` | Update node (title, position, type, etc.) |
| `POST /api/books/{id}/nodes` | Create node |
| `DELETE /api/books/{id}/nodes/{id}` | Delete node |
| `POST /api/books/{id}/nodes/{id}/choices` | Create choice/connection |
| `DELETE /api/books/{id}/choices/{id}` | Delete choice |
| `GET /api/books/{id}/acts` | Load acts |
| `POST /api/books/{id}/acts` | Create act |

## Known Issues / Decisions Made

1. **Debounced save** — node positions are saved 300ms after the last mouseup, not on every drag end. This avoids thrashing the API during fine adjustments. The `_saveTimeouts` Map tracks in-flight saves to prevent duplicates.

2. **Undo limited to 20 steps** — the undo stack is bounded. This was a deliberate tradeoff: canvas state is always persisted to the database, so the undo is a convenience, not a persistence mechanism.

3. **Validation endpoint not wired** — the `GET /books/{id}/validate` endpoint exists in the backend but returns a stub ("no issues found"). Will be connected in Phase 3.

4. **No save-to-disk JSON export** — the "Load JSON" and "Export" buttons are in the toolbar but not wired to actual file I/O yet.

5. **No Pydantic schemas on frontend** — all API calls send raw objects. Type safety is only enforced by the backend.

6. **Connection drawing order** — connections are drawn before nodes so they appear underneath. Arrowheads are positioned at the exact edge of the target node rectangle, not at the center.

## What's Next — Phase 3

- Act management view with entry/exit node selectors
- Graph validation engine in UI (status bar with errors/warnings)
- Node type enforcement (at least one entry, at least one ending per book)
- Act continuity checks (no dangling choices, no unreachable nodes)
