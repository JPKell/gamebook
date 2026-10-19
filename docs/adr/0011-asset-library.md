# ADR 0011: Content-addressed asset library and polymorphic art placements

**Status:** Accepted (2026-10-18)

## Context
Phase 10 adds images: a per-series library, art placed on nodes, acts, books and entities
with print layout controls, maps and generated appendices. We needed to decide:
- where image bytes live
- how they survive undo, checkpoints and export
- how a placement points at its many kinds of target

## Decision
- **Files are content-addressed outside SQLite.** Each image lives at
  `<data_dir>/assets/<sha256>.<ext>`, with a WebP thumbnail at `assets/thumbs/<sha256>.webp`.
  - Rows (`asset`) hold metadata and are unique per series and hash. The same file can
    back rows in several series.
  - Writes are atomic: a temporary file, then a rename.
- **GC respects checkpoints.** A file is deleted only when no `asset` row in the live
  database, and none in any checkpoint database, names its hash. Restoring a checkpoint
  therefore never finds its images gone.
  - A checkpoint that can't be read aborts GC.
  - Files touched in the last 15 minutes are kept, so an upload reusing a file is never
    caught mid-commit.
  - GC runs after asset deletes, series deletes, import replaces and on demand.
- **One placement table, a foreign-key column per target kind.**
  - The kinds are node, act, book, character, enemy, item and lore, with `ON DELETE CASCADE`.
    Placements go when their target does, without application code.
  - `asset_id` is `SET NULL`: deleting an image leaves a placeholder with its brief.
  - `variant_id` cascades: art limited to a deleted text variant goes with it. Showing it
    to every reader could spoil the other branches.
- **Undo covers book art.** Node, act and book placements are serialised in the
  `export_book` snapshot (`art:` in node front matter, `act.yaml` and `book.yaml`), so
  undo/redo and git export restore them.
  - Entity portraits travel in the entity files and aren't undoable, like the entities
    themselves.
  - Maps and appendices are exported, but not in undo snapshots.
- **Assets in the RefIndex.** Placements and maps are RefIndex sources whose target is the
  asset's id (assets have no key). Where-used, the delete guard and "unused asset" all come
  from the index, like every other reference. Placement rows are dropped from the index
  before cascades remove the placements.
- **Exports carry the binaries.** `assets.yaml` holds the metadata. The zip and folder
  exports add `assets/<sha256>.<ext>` (stored uncompressed in the zip). Import checks each
  file's hash before writing it to the store.
- **Appendices render server-side.** Autoescaped Jinja templates in `gamebook/render/` are
  shared by the preview, the player's codex and (Phase 11) print/EPUB. Author text uses a
  minimal Markdown subset that can't emit raw HTML.

## Consequences
- The database stays small, and checkpoints stay cheap: they copy rows, not images.
- Files can outlive their rows until GC runs.
- The placement table carries several mostly-empty columns. In exchange, cascades and
  per-target queries are plain SQL, and a check constraint isn't needed because only
  services write placements.
- Print geometry is pure (`core/art.py`) and shared by the API, problems and the shot
  list. Phase 11 lays out pages from the same numbers.
