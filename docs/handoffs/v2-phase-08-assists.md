# v2 Phase 8 — LLM authoring assists

**Status:** Complete · **Date:** 2026-10-18 · **Branch:** `v2`

Built and tested against the offline model only. The user was benchmarking their own LLM server at the time, so no real endpoint was contacted.

## What was built

### Backend
- **Migration 0007:** the `assist_item` table, one row per thing an assist proposes.
  - `kind`: `finding`, `suggestion` or `lore`.
  - `status`: open / partial / accepted / rejected / dismissed / superseded.
  - Also a kind-specific `payload`, and `checked_hash` for findings.
- **Templates (`llm/templates.py`):** defaults and JSON schemas for three new roles: `consistency`, `suggester`, `lore_extractor`. Existing databases get them seeded as v1 on first use.
- **`llm/fake.py`:** deterministic behaviour for the new roles.
  - Consistency flags prose that names a "only some readers have" item.
  - The suggester adds one section per uncovered beat, linked from the last open section and on to the first ending.
  - The extractor finds "named X" (a character) and "called the X" (a location).
- **`services/assist.py`:**
  - **Consistency:** runs per section, act or book; findings per variant are superseded on re-check, become outdated when the prose changes, and feed Problems.
  - **Suggester:** output is validated (`_clean_suggestion`). Accepting is piecemeal; a choice brings its new ends; placement uses `free_spot`; the whole accept is one undo step.
  - **Lore extractor:** approved prose up to about 24k characters, de-duplicated against open drafts. Accepting creates the entity, or appends new facts to the existing one.
- **API:**
  - `POST /nodes/{id}/consistency`, `POST /books/{id}/consistency {act_id?}`
  - `POST /acts/{id}/suggest {notes}`
  - `POST /books/{id}/extract-lore {act_id?}`
  - `GET /books/{id}/assist?kind&status&node_id`, `PATCH /assist/{id} {status}`
  - `POST /assist/{id}/accept-suggestion|reject-suggestion {nodes, choices}`, `POST /assist/{id}/accept-lore {fields}`
  - Problems now include open, current findings (`consistency`).
- **New test:** API operation ids must be unique (route names collided once and mixed up the generated client types).

### Frontend
- **Story canvas:**
  - A **Suggest** toolbar button opens a dialog (act and notes).
  - Suggested sections appear as dashed **ghost cards** (Add section / Dismiss), with dashed animated edges for suggested choices.
  - A **Suggestions bar** above the canvas lists the choices (Add / Dismiss each, Add all, Dismiss all).
  - Ghost sizes are tracked so React Flow settles. Ghosts are selectable (needed for their buttons) but their selection is ignored.
- **Writing:**
  - A **Consistency** panel per section ("Check this section", findings with quote, problem and suggestion, Dismiss, outdated marker).
  - A **Check consistency** button for the whole book in the header, with progress and the result count.
- **Lore → From prose:** read a book's (or one act's) approved prose, then review draft cards. Each card shows evidence, editable fields and a type; "Create" or "Add to entry", or Reject.
- **Settings:** the three new roles appear in Prompt templates and Pipeline settings.

## Bug pass (independent review)
An independent reviewer confirmed 15 findings. All are fixed and covered by regression tests.

- **Security: accepting a lore draft could write any column.** For example, it could change an existing entity's `key` or `series_id`. Accepting now whitelists fields per target (character text fields + name; lore name/type/body). It merges only new text, through `entities.update_entity` (validation + ref index). If the entity was deleted it returns 409.
- **Lore across books:** a draft could match another book's entity. Matching is now limited to entities shared by the series and this book's own.
- **Lore extraction limits:**
  - Sections that don't fit the character budget are now skipped (and counted), not cut off at the first one that overflows.
  - Rows are capped at 30 and values clipped.
  - An `act_id` from another book returns 422.
  - Cancelling while the model is reading writes nothing.
- **Status transitions** follow an explicit table; closed items return 409.
- **Undo after a partial accept** re-syncs the suggestion with what still exists.
- **Accepting with nothing to add** no longer writes a history entry.
- **Dismissed findings** stay dismissed when the prose is checked again unchanged.
- **Book check:** one deleted section no longer fails the whole check. Book data loads once per job, not once per section.
- **Suggester caps:** 20 issues per check; 20 nodes and 40 choices per suggestion. An empty reply keeps the previous suggestion.
- **Deleted sections and acts:** findings for deleted sections are hidden. Suggestions for a deleted act are superseded, and accepting one returns 409.
- **Ghost placement:** the backend stores each ghost's x/y and the canvas uses it, so cards don't jump when accepted.
- **Frontend:**
  - Findings show per variant.
  - Lore drafts no longer hide fields on new entries.
  - The suggest result counts choice-only suggestions and says when there is nothing new.
  - The book check reports sections it couldn't check.
- **Accessibility:** ghost cards are labelled groups; their buttons and the choice buttons name what they act on; Dismiss names the finding.


## Tests
- **Backend:** 435, plus 1 opt-in live test.
  - `test_assist.py`: findings reach Problems, go outdated, are superseded and dismissed; prose is required; suggestions accepted piecemeal (choice brings its node, clear placement, undo, closed → 409); suggester output validation; lore create and merge with no duplicate drafts; field whitelist, deleted entity → 409, other books' entities ignored, deleted sections and acts drop out.
  - Plus the operation-id uniqueness test.
- **Frontend unit:** 57.
- **Browser:** 24. New in `e2e/assist.spec.ts`: ghost sections on the canvas (add a section, add a choice, add all), the consistency panel with dismiss, lore drafts created from prose.

## Known issues / notes
- Suggestions place new sections with a simple "move down until free" rule; auto-layout tidies up.
- Lore merging appends text (deduplicated by exact containment); it doesn't rewrite or reconcile contradictions.

## Phase 9 starting points
1. **LLM players** reuse `llm.call_json` with a `player` role and JSON schema; the stateless player (`services/play.py`) already renders what a reader sees.
2. **Playtest batches** gain an LLM player kind (`BotPlayer` → union) with budget caps and concurrency (the job runner is single-threaded; LLM batches may need their own worker or async calls).
