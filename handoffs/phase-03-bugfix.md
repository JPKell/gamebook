# Phase 3 — Bug Pass & Stability Fixes

**Date:** 2026-10-12
**Status:** Complete
**Previous Phase:** Phase 2 (Graph Canvas) — `handoffs/phase-02-canvas.md`

---

## What was done

A thorough bug pass was performed on the frontend and backend to fix critical
issues that prevented the app from being usable: clicking "New Series" did
nothing, the canvas never appeared after selecting a book, and the database
had no tables.

## Bugs fixed

### 1. Toolbar buttons had no `data-action` attributes (frontend)

**File:** `app/static/index.html`

The `handleClick` function in `app.js` delegated clicks through
`[data-action]` selectors, but the toolbar buttons (`#btn-new-series`,
`#btn-save`, `#btn-load`, `#btn-export`, `#btn-preview`, `#btn-validate`)
lacked these attributes entirely. Only sidebar elements had them.

**Fix:** Added `data-action` attributes to all toolbar buttons matching their
intended action names (`new-series`, `save`, `load`, `export`, `preview`,
`validate`, `undo`).

### 2. Toolbar action handlers were missing (frontend)

**File:** `app/static/js/app.js`

The `handleClick` function only handled sidebar actions (`select-series`,
`select-book`, `new-act`, `new-node`, etc.). The toolbar actions (`new-series`,
`save`, `load`, `export`, `preview`, `validate`, `undo`) were handled in
separate individual event listeners that were sometimes stale or missing.

**Fix:** Integrated all toolbar actions into `handleClick` using the unified
`data-action` delegation pattern. This includes:
- **new-series** → opens the "Create Series" modal
- **save** → shows "auto-save on node drag" status (auto-save is already wired)
- **load** → prompts for a JSON file and imports it
- **export** → calls the existing `/series/:id/export` API and downloads JSON
- **preview** → opens the in-app preview overlay (implemented from scratch)
- **validate** → calls `validate_graph()` locally and reports issues
- **undo** → calls the existing `undo()` function

### 3. `runValidation()` and `startPreview()` were not implemented (frontend)

**File:** `app/static/js/app.js`

Both buttons had TODO placeholders. The validation button said
"not yet implemented" and preview did nothing.

**Fix:**
- **Validation** (`runValidation`): Calls the existing `validate_graph()`
  function (defined in the same file) with acts, nodes, and choices. Reports
  errors and warnings in the status bar. Validation logic itself (the
  `validate_graph` function) was already present in the canvas code.
- **Preview** (`startPreview`): Implemented a full in-app story preview. It
  finds entry nodes, renders node content (title, description, items,
  encounters, choices), supports forward navigation through choices, and
  includes a "Back" button. Works entirely in the browser — no API calls.

### 4. `drawGrid` referenced bare `canvas` variable (frontend)

**File:** `app/static/js/app.js`

The `drawGrid(ctx)` function used `canvas.width` and `canvas.height` directly,
but `canvas` was not in scope (only `ctx` was passed as a parameter). This
would have caused a JavaScript error when the canvas tried to draw.

**Fix:** Looked up `canvas` and its container from the DOM inside the function,
and switched to using `container.clientWidth` / `container.clientHeight` for
the visible area calculation (more accurate than canvas dimensions which may
differ due to CSS scaling).

### 5. `drawZoomIndicator` drawn with transform active (frontend)

**File:** `app/static/js/app.js`

`drawZoomIndicator(ctx, canvas)` was called after `ctx.restore()` but the
zoom text would still be drawn at the wrong position because the transform
wasn't reset.

**Fix:** Added `ctx.setTransform(1, 0, 0, 1, 0, 0)` before drawing the zoom
percentage text so it appears in fixed screen coordinates.

### 6. Dead code in `get_series` route (backend)

**File:** `app/routes/series.py`

The `get_series` endpoint had a convoluted books query using
`Series.books.property.mapper.class_` that was immediately overwritten by a
simple `session.query(Book)` call. The import statements for Book, Location,
Item, Encounter were also dead.

**Fix:** Removed the dead code, leaving only the simple query.

### 7. Database tables not auto-created on startup (backend)

**File:** `app/__init__.py`

The `lifespan` function had a TODO comment and did nothing. When the service
was restarted or the database was fresh, tables didn't exist and every API
call returned 500 Internal Server Error.

**Fix:** Added `Base.metadata.create_all(engine)` in the lifespan startup event.
This is idempotent and safe to call on every server start.

### 8. Models not exported from `app.models.__init__.py` (backend)

**File:** `app/models/__init__.py`

The `__init__.py` only had a docstring — no imports. This meant that
`from app.models import Series` etc. would fail. This also broke any code
that relied on importing models from the package.

**Fix:** Added imports for all 8 models and an `__all__` list.

## Files modified

| File | Change |
|------|--------|
| `app/static/index.html` | Added `data-action` attributes to all toolbar buttons |
| `app/static/js/app.js` | Integrated toolbar actions into `handleClick`; implemented `runValidation()` and `startPreview()`; fixed `drawGrid` scope; fixed `drawZoomIndicator`; removed dead `renderWithBack` code; removed duplicate inline event listeners |
| `app/routes/series.py` | Removed dead code in `get_series` |
| `app/__init__.py` | Added `Base.metadata.create_all()` to lifespan startup; added `engine.dispose()` on shutdown |
| `app/models/__init__.py` | Added model exports and `__all__` list |

## Verification

- All 8 integration tests pass (`pytest tests/`)
- Backend smoke test: `POST /api/series/` returns a valid series with UUID
- Frontend: `GET /` serves `index.html` with correct `data-action` attributes
- Service is running on `0.0.0.0:8788`

## What's next (Phase 4)

Phase 4 (Preview) has been partially delivered in this pass — the in-app
preview mode is implemented. Remaining work for a polished Phase 4:

1. **Story text rendering** — If nodes have `storyText` populated (from AI
   generation), the preview should show that instead of the node's
   description.
2. **Inventory tracking** — Items picked up on one node should persist
   through the preview session.
3. **Multiple endings tracking** — Track which ending nodes were reached
   and how many times.
4. **End-of-game summary** — Show a recap of all paths taken and endings
   reached.
5. **Preview from entry point** — Allow starting preview from any node,
   not just the first entry node.

Phase 5 would then be polishing the UI, adding animations, and refining
the canvas UX.
