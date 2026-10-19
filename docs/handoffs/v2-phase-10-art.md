# v2 Phase 10 — Artwork, maps & appendices

**Status:** Complete · **Date:** 2026-10-18 · **Branch:** `v2`

## What was built

### Backend
- **Dependency:** Pillow (image checks and thumbnails).
- **Migration 0009:**
  - Tables `asset`, `art_placement`, `map` and `appendix`.
  - A new `book.print_setup` column.
- **`core/art.py`** (pure):
  - `PageSetup` (trim, margins, bleed in mm).
  - `PrintLayout`:
    - size presets with bleed, custom mm or %, and a maximum height
    - position, including after paragraph N, own page (recto/verso) and facing page
    - align, wrap and gutter
    - crop aspect with a focal point
    - keep-with
  - `DigitalLayout` (full width / inline / thumbnail, tap to zoom).
  - `print_size` returns the printed size, effective DPI and status: good ≥ 300, low ≥ 150, poor.
  - Also `crop_box`, `pixels_needed` and per-role defaults: act openers are recto full pages, covers bleed, portraits are thirds wrapped right.
- **`services/assets.py`:**
  - The content-addressed `Store` (`data_dir/assets`), with atomic writes.
  - Pillow probing: PNG/JPEG/WebP only, 40 MB and 160 Mpx caps, decompression-bomb guard.
  - 480 px WebP thumbnails; upload dedupe per series.
  - Metadata editing; where-used through the RefIndex.
  - Deletion is guarded: forcing it turns placements into placeholders.
  - GC keeps any hash named in the live database or any checkpoint.
- **`services/art.py`:**
  - Placements:
    - create, update, delete and reorder
    - target and role validation, and variant/tier limits
    - undo history for node, act and book art
  - Page setup, with validation.
  - Canvas thumbnails, and digital art for the player.
  - The shot list, as JSON, CSV or Markdown.
  - Maps: markers are validated (unique ids, sections in the map's book, lore in the series, gbx `visible_if`).
  - Art problems, listed in the book's Problems.
- **`services/appendix.py` + `render/`:** the eight kinds, rendered through autoescaped Jinja templates.
  - **Bestiary:** stat blocks per tier at the levels used, or a level table, plus portrait and lore link. Ordered A–Z or by first appearance.
  - **Adventure sheet:** stats, class and skills checkboxes, slots, currency, inventory lines, codewords set in the book.
  - **Item catalogue:** with tier modifiers and use effects in English; key items can be hidden.
  - **Rules reference:** tests, combat, flee, plus each tier's rules text.
  - **Also:** dramatis personae, glossary, maps with a numbered legend, and custom Markdown.
  - **Options:** spoiler policy (all, or main path only) and blank entries.
  - **Codex:** the enabled appendices, with bestiary and items limited to what the reader has met.
- **Player (`services/play.py`):** `PlayOut.art`, `PlayOut.maps` (markers filtered by `Game.holds(visible_if)`, the current section flagged) and `PlayOut.codex`.
- **RefIndex:**
  - `placement` and `map` sources point at `asset` targets; map markers point at nodes and lore.
  - Placement rows are dropped when nodes, acts or entities are deleted.
  - The full rebuild includes both.
- **Git tree:**
  - Placements go in node front matter, `act.yaml`, `book.yaml` and entity files (`art:`).
  - `book.yaml` carries `print_setup`.
  - New files: `maps/<key>.yaml` (series or book), `books/NN/appendices.yaml`, `assets.yaml`, and binary `assets/<sha>.<ext>` (stored in the zip). Import checks each file's hash.
  - `restore_book` (undo) rebuilds book and act placements.
- **API (`routers/art.py`):**
  - assets: upload, list, edit, delete, where-used, file, thumbnail, GC
  - placements: CRUD and reorder
  - `GET/PUT /books/{id}/page-setup`
  - maps: CRUD
  - appendices: CRUD, reorder and `/render`
  - `POST /books/{id}/codex`
  - `GET /series/{id}/shot-list?format=json|csv|md`
  - The book graph's nodes now include `art_thumb`.

### Frontend
- **Art section (`/art/:seriesId`):**
  - **Library:** drop or browse to upload; filter; thumbnail grid with use counts and a "no alt text" flag; detail panel with metadata, print size at 300 dpi, where-used links, and a delete guard.
  - **Book art:** page setup with a page diagram; covers and front matter; an act opener per act.
  - **Maps:** create a map and pick its image; click to add markers, nudge them with the arrow keys; link each to a section or place; set "only shown if" conditions.
  - **Appendices:** add, reorder and enable; per-kind options; a live preview in a sandboxed iframe.
  - **Commissioning:** every placement with its brief, printed size and pixels needed; status edited inline; Markdown and CSV exports.
- **`PlacementList` / `PlacementEditor`**, shared by the node Art tab, book art and entity portraits:
  - image or placeholder, role, status, media, variant, tier, caption, brief
  - print controls with a live DPI badge, a page preview (trim, bleed, safe area) and a focal-point picker
  - digital display settings
- **Story:** an inspector **Art** tab, and thumbnails on canvas cards.
- **Entities:** a Portrait panel on enemy, item, character and lore editors.
- **Player:** section art (with zoom), a **Map** panel with "you are here", and a **Codex** panel.
- **`useLatest`:** quick successive edits to one layout, options or marker list merge instead of overwriting each other. The map editor keeps a local marker list for the same reason.

## Bug pass (independent review)
An independent reviewer confirmed 9 findings plus nits. All are fixed and covered by regression tests.

1. **Security: importing an archive could read arbitrary files.** `assets.yaml` hashes weren't checked to be hex, so a crafted `../` "hash" served any `.png`/`.jpg`/`.webp` file on the machine. The YAML's `mime` could also make a PNG/HTML polyglot serve as `text/html` (stored XSS).
   - Hashes must now be 64 hex characters, and the store refuses any other name.
   - Type and size come from probing the image, never from the YAML.
   - Entries with no image (in the zip or the store) are skipped, so their placements become placeholders.
   - Files are served with the type of our own extension and `X-Content-Type-Options: nosniff`.
2. **Non-image blobs in an import crashed with a 500** and left a file behind. Every blob is probed, and a bad one returns 422. The thumbnail is made before anything is written.
3. **The decompression-bomb limit was effectively doubled.** Pillow only errors at 2× its limit; a 289 Mpx PNG was accepted and decoded. `probe` now rejects anything over 160 Mpx itself, before decoding.
4. **A truncated JPEG passed the check, then crashed thumbnailing.** `probe` now decodes the pixels (`load()`); nothing is written for a bad file.
5. **The codex leaked spoilers and used the wrong tier.** Map markers hidden behind conditions showed, and rules rendered for the highest tier. Every codex page now uses the reader's tier, and the codex never shows conditional markers (the player's map shows the revealed ones).
6. **Deleting a text variant showed its art to every reader.** The variant foreign key now cascades, and the placement's index rows are dropped.
7. **GC could delete images an unreadable checkpoint needs.** A checkpoint that can't be read (corrupt, locked, half written) now aborts GC with a 409. Only checkpoints from before the asset table existed are skipped. GC after a delete logs and keeps everything.
8. **EXIF orientation was ignored.** Sizes and thumbnails now follow the orientation browsers display, so DPI, crop and the pixels needed are right.
9. **GC could race an upload reusing a file.** Reusing a file refreshes its mtime, and GC never touches files written or reused in the last 15 minutes.

Nits also fixed:
- **Series-wide maps:** markers linking deleted sections in any book of the series are reported.
- **Tiers:** placement and appendix tiers are checked against the rule system (422).
- **Item catalogue:** it honours first-appearance order (with a control in the UI), and its codex total leaves out hidden key items.
- **GC:** it runs after a series delete and after an import with replace.
- **Shot list CSV:** cells that a spreadsheet would run as formulas are quoted.
- **Imports:** duplicate `assets.yaml` entries return 422 instead of a 500.
- **Map editor:** it shows the server's markers again when a save is refused.

## Tests
- **Backend:** 472, plus 1 opt-in live test.
  - `tests/api/test_art.py` (18, including 8 regressions from the review):
    - upload, dedupe, file and thumbnail serving, format rejection, tags
    - DPI following size, bleed and page setup, with problems and the canvas thumbnail
    - placeholders, roles and the shot list (CSV/Markdown escaping)
    - undo/redo of node art
    - the delete guard and checkpoint-safe GC
    - unused-asset and alt-text problems
    - maps in the player, with codeword-revealed markers and broken-marker warnings
    - digital art per media
    - appendices: tier stats, portraits, blank entries, Markdown escaping, reorder, codex unlocks
    - an export/import round trip that restores a missing file and is deterministic
  - `tests/core/test_art.py` (8): geometry, crop, bleed, placeholders, the Markdown subset.
- **Frontend unit:** 59, including `useLatest`.
- **Browser:** 28. New in `e2e/art.spec.ts`:
  - upload, place, DPI change and canvas thumbnail
  - act opener placeholder, shot list, map marker shown in the player
  - bestiary and sheet previews, codex start state

## Known issues / notes
- Previews and the codex link images with `/api/assets/...` URLs. Print (Phase 11) will pass a file resolver (`render_appendix(asset_url=...)`).
- Keep-with, facing page and after-paragraph positions are stored and shown, but only the print compiler (Phase 11) can honour them.
- A series-wide map can link sections in any of its books. The editor offers section links only for book maps.
- GC runs after asset deletes, series deletes and import replaces. Deleting a checkpoint leaves its files until the next GC (`POST /assets/gc`), and files touched in the last 15 minutes are always kept.
- `asset_unused` is a series-level fact, so it is reported in every book's Problems.

## Phase 11 starting points
1. Print layout uses `core/art.print_size` and `PageSetup` for every placement. Appendices render with `render.appendix.fragment(...)` and the templates' CSS.
2. Section numbering and the compiler can read `PrintLayout.position`, `page_side` and `keep_with` from placements.
3. EPUB: each asset's alt text, caption and credit are on the row, and digital layouts apply to e-readers too.
