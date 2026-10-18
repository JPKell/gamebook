# ADR 0005 — Server-side undo via book snapshots

**Status:** Accepted (2026-10-18)

## Context
The editor needs reliable undo/redo for every kind of change: moves, deletes (with
cascades and SET NULL side effects), renames that rewrite references across the series,
duplicate-with-remap, act reorders. Client-side inverse operations would need a correct
inverse for each of ~25 endpoints, including server-side side effects the client can't
see, and would be lost on reload.

## Decision
Before each book-scoped change, the API stores a snapshot of the book's story graph
(`export.tree.export_book`, the same code as the git export) in `history_entry`. Undo
restores the latest snapshot (`restore_book`) and pushes the current state onto the redo
stack; any new change clears redo. 50 entries per book; edits with the same label within
10 s coalesce (typing). Entities (items, enemies, lore) are series-level and outside a
book's undo — if a snapshot refers to an entity deleted since, undo is refused with a clear
message rather than restoring a broken graph.

## Consequences
Every edit is undoable with identical semantics, history survives reloads, and the
snapshot code is exercised constantly (it is also the export path). Cost: one book export
per edit — milliseconds for typical books; revisit (e.g. diff-based storage) if books reach
thousands of nodes.
