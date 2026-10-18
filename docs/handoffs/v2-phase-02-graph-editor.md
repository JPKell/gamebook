# v2 Phase 2 — Story graph editor

**Status:** Complete · **Date:** 2026-10-18 · **Branch:** `v2` (uncommitted at time of writing)

## What was built

### Library (`frontend/src/features/library/`)
- Series cards with their books; create series/book (new books open straight onto the canvas), delete with confirmation.
- Series settings dialog: title, description and the **style guide** (POV, tense, word range, voice, writer notes).

### Story canvas (`frontend/src/features/story/`)
- **React Flow** canvas for the whole book. Acts are colour-coded frames computed around their nodes (empty acts get a placeholder frame with a "+" to add a node).
- **Node cards**: key, roles (start/entry/exit), title, beat-note preview, ending badge, problem counts, and badges for encounters, items, shop, gated choices, effects and variants.
- **Edges**: one per targeted outcome. Kind shown by colour and icon (roll, test, combat), conditional choices dashed, cross-act edges thicker, labelled with the choice text plus outcome or roll range.
- **Interactions**: drag-to-link (creates a goto choice), drag to empty space (creates a linked node), double-click empty canvas (new node), drag into another act's frame (moves it to that act), multi-select, delete (API-backed and undoable), click an edge (opens its choice), minimap, zoom controls.
- **Toolbar**: + Node, undo/redo with the action named in the tooltip, search (highlights matches and dims the rest, with a count), filters (problems, gated, encounters, items/shop, endings), ELK **auto-layout** per act (left to right), fit, and Book & acts.
- **Shortcuts**: N new node · F fit · Ctrl/⌘+F search · Ctrl/⌘+Z / Shift+Z / Y undo/redo · Ctrl/⌘+C/V/D copy/paste/duplicate · Delete · Esc. Shortcuts are ignored while typing.
- **Book & acts dialog**: rename, colour, summary, reorder, add/delete acts (force when an act has nodes); book title, number and synopsis.

### Inspector (side panel, tabs)
- **Header**: title, key (renaming updates references), act select, start-node toggle, duplicate, delete.
- **Beat**: beat notes (autosave), summary, act entry/exit, ending kind/grade/name, on-entry effects, section pin.
- **Choices**: cards for every kind.
  - **Goto**: destination.
  - **Roll**: dice plus ranged outcomes, add/remove.
  - **Test**: rule-system test with success/failure.
  - **Combat**: this node's encounter, flee option, win/lose/flee.
  - **All kinds**: condition, unmet display, minimum tier, print-text override, and effects; reorder and delete.
- **Encounters**: fixed groups (enemy, level, count; one at a time or all at once) or random table, items found here, shop (sell rate; items with price and stock). Includes inline "+ New enemy/item…".
- **Variants**: conditional text variants with priorities.
- **Lore**: location, characters present, story-so-far predecessor.

### gbx editor (`frontend/src/components/gbx/`)
- CodeMirror single-line field with syntax highlighting and context-aware autocomplete:
  - items after `has(`/`count(`/`equipped(`
  - codewords after `flag(`
  - skills and classes after `skill(` / `class(`
  - node keys after `visits(`
  - stats after `player.`, plus functions, tiers and context variables
- Debounced server check gives squiggly diagnostics, an **English preview**, and for dice the range and most likely result. Commits on blur or Enter; Escape reverts.

### App shell
- **Breadcrumb**: series › book with a book switcher.
- **Problems panel** (Ctrl/⌘+J): live validation for the open book; click a problem to select its node or choice and centre it.
- **Command palette**: jump to any node of the open book.
- **Checkpoints dialog** (history icon): save, restore with a safety checkpoint, delete.
- **Toasts** for errors and undo, and a Library nav item. Story and Library pages and ELK load lazily: the initial bundle went from 2.6 MB to 568 KB.

### Backend additions
- **Undo/redo** (ADR 0005): `history_entry` table (migration `0003`), `services/history.py`, recording on every book-scoped mutation endpoint, `GET /books/{id}/history`, `POST /books/{id}/undo|redo`. Works through `export.tree.export_book` / `restore_book`, refactored out of the series export.
- **Checkpoints**: `services/checkpoints.py` (SQLite online backup), `GET/POST /checkpoints`, `POST /checkpoints/{id}/restore`, `DELETE /checkpoints/{id}`.
- **Auto keys follow titles**: if a key was derived from the old title or name, renaming carries the key along and rewrites references. Hand-picked keys never move.
- Generated TS types now use `--default-non-nullable false`, so request fields with server defaults are optional.

## Bugs found and fixed during the phase
- **Commit after response (backend, important):** FastAPI's default for `yield` dependencies runs teardown *after* sending the response. A client refetching right after a write could read stale data, and a failed commit would still have returned success. `SessionDep` now uses `scope="function"`. The regression test fails without the fix.
- **Stale first-load refetch (frontend):** invalidating a query whose first fetch was still in flight reused that pre-write request. `refresh()` now cancels in-flight fetches before invalidating, with a regression test that fails without it.
- **Selection echo:** React Flow's `onSelectionChange` echoed programmatic selections back as empty. The store is now the single source of truth; user selections arrive via `select` node changes.
- `TextInput` lost edits when it unmounted mid-edit; it now commits on unmount. New nodes no longer land on top of existing ones.
- Phase 1 review fixes are listed in `v2-phase-01-domain.md`.

## Tests
- **Backend**: 229 (adds history, checkpoints, commit-before-response, auto-key regressions).
- **Frontend unit**: 34 (flow conversion, frames, act hit-testing, search/filters, auto-layout, inputs including unmount commit, Library, refresh race).
- **Browser (Playwright)**: 7. Library → book, add and rename a node, link via a choice, undo/redo by keyboard, reload persistence including history, problems-panel navigation, delete plus undo, drag-to-create, live gbx feedback. 8 consecutive full runs at 4 workers were green.

## Decisions
- Server-side snapshot undo instead of client inverse operations (ADR 0005).
- Act frames are computed from node positions, not React Flow parent/child groups. Nodes keep absolute coordinates, which matches the database, and frames can't drift.
- Native `<select>` for pickers (accessible and fast). A searchable picker can replace it if node counts make lists unwieldy.

## Known issues / notes
- Book style overrides are stored, but the editor only exposes the series guide (Phase 7 is where they matter).
- The Enemies, Items, Lore and Mechanics sections are still placeholders. Inline "+ New…" creates entities by name only.
- Self-loop edges render as a small hook; acceptable for now.
- `HistoryEntry` stores full snapshots: fine at current scale, revisit for very large books (ADR 0005).

## Phase 3 starting points
1. Engine in `core/engine/` on top of `core/model.BookSnapshot` + `rules.effective_tier`; seeded `SeededRng` from gbx records rolls.
2. Mechanics designer UI: edit `RuleSystemDef` (already validated server-side) with tier tabs; reuse `GbxField` with contexts `stat_initial`, `test_roll`, `test_success`, `combat_attack`, `combat_damage`.
3. Combat lab endpoint: Monte Carlo fights against `Enemy.stat_formulas` at a level range.
4. Golden-trace format for future TS parity.
