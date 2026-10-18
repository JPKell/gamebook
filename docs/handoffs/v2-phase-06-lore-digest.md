# v2 Phase 6 — Lore, outline, state digest

**Status:** Complete · **Date:** 2026-10-18 · **Branch:** `v2`

## What was built

### State digest (`core/analysis/digest.py`, pure)
- **The analysis:**
  - Forward dataflow to a fixpoint: per-node **must** and **may** codewords, items, characters met and skills (SPEC §2.9).
  - Arrival state is taken after on-entry effects.
  - Edges add, in order: optional pickups, shop buys and sells, and consumable use (and their effects) as "may"; what the condition proves; the choice's effects; a test's after-effects; table drops.
  - Choices no reader can take are skipped.
- **Gate verdicts:** `judge()` is three-valued over `has`, `flag`, `skill`, `equipped`, `count(x) >= n`, `not`, `and` and `or`.
- **Depths:** shortest by BFS; longest by Tarjan SCC condensation, unbounded through loops.
- **Canonical predecessor:** the first node on a shortest route, in choice order.
- **Core model changes:** `Node.character_ids`, `Node.canonical_predecessor_id`, `Beat`, `BookSnapshot.beats`. Golden traces were regenerated; only these bundle fields changed, not engine events.

### Validation
- **From the digest** (at the highest tier):
  - `gate_never` (warning): no reader can take a choice.
  - `gate_always` (info): every reader can.
  - `trapped` (warning): an ending is reachable on paper but only through impossible choices.
  - `bad_canonical` (warning): the overridden predecessor has no choice leading here.
- **Outline** (only in acts that have beats): `beat_empty` and `node_no_beat` (info).

### Outline & lore backend
- **Beats:** tables `story_beat` and `story_beat_node` (migration 0005), ordered and linked to nodes; a deleted node drops out of its beats.
  - Beats are part of undo history, and of export/import via `act.yaml`. The round-trip test now includes beats and compares outlines.
- **Endpoints:**
  - `GET /books/{id}/outline`
  - `POST /acts/{id}/beats`, `PATCH /beats/{id}`, `DELETE /beats/{id}`, `PUT /acts/{id}/beats/order`
  - `GET /books/{id}/digest?tier=`, `GET /nodes/{id}/digest?tier=`: facts with labels, gate verdicts, depths, and canonical auto/override/effective.
- **Mentions:**
  - **Syntax:** `[[key]]`, `[[character:key]]` / `[[lore:key]]`, with optional `|label`.
  - **Where:** node beat notes, character text fields and relationship notes, lore bodies, and beat descriptions.
  - **Indexing:** RefIndex rows with role `mention`. Lore entries and beats are now ref sources, and `rebuild_series` includes them.
  - **Renames:** a key rename rewrites mentions, keeping prefixes and labels.

### Frontend
- **`/lore/:seriesId`** has three views: Characters, Places & lore, and Outline.
  - **Character editor:** role, appearance, voice, motivations, secrets, notes (with mention previews), relationships, appearances, and "Mentioned in".
  - **Lore editor:** type, text with a live mention preview, "Scenes set here" for locations, and backlinks.
  - **Outline:** per book; act summaries and beats (rename, describe with mentions, link/unlink nodes, reorder, delete), plus a "not in any beat yet" list.
- **`MentionText`:** paragraphs with resolved mentions as links. Broken mentions are dashed red with a tooltip. The resolver is unit-tested (`mentions.test.ts`).
- **Story inspector, new Digest tab:**
  - "Reached after N choices".
  - **Every reader has** (solid chips) and **Some readers have** (dashed).
  - Gated choices with always/never/depends verdicts (click to open the choice).
  - Story so far (the canonical predecessor, automatic or chosen) and the beats this node belongs to.
  - The Lore tab's "Story-so-far comes from" shows the automatic choice.
- **Where-used lists:** non-node sources (characters, lore, beats, enemies, items, tables) now link to their editors, and lists can be filtered by role.

## Bug pass (independent review)
Seven findings, all fixed, with regression tests:
1. **Force-deleting a mentioned character or lore entry crashed with 500.** The targeting refresh had no models for lore and beat sources. There is now one shared `refs.SOURCE_MODELS`.
2. **Beat references went stale** after undo/redo of beat edits, undoing "Add beat", and deleting an act. `restore_book` now drops and reindexes beat sources, and deleting an act drops its beats' rows. Tested against a full rebuild.
3. **Once-only gains in loops were wrongly "must".** A give that doesn't fire again after a take caused false `gate_never` and `trapped` warnings. A once-only gain on a node or choice inside a loop is now only "may" when something in the book can remove that fact.
4. **Performance.**
   - Consumable effects are precomputed and applied to a fixpoint, which also fixes consumables that grant other consumables.
   - The inspector reads the whole-book digest once per edit instead of once per node selection.
   - Timings for generated, loop-heavy books:

     | Book | Before | After |
     |---|---|---|
     | 1,000 nodes, 200 items and flags | 10.2 s | 1.8 s |
     | 3,000 nodes, 300 items and flags | 78 s | 8.5 s |
     | 1,000 nodes, 80 items and flags | — | 0.6 s |
5. **Impossible choices still counted for reachability, depth and the canonical predecessor.** These now use only choices someone can take. A new warning, `unreachable_gated`, covers nodes reachable only through impossible choices.
6. **Consumables drunk mid-fight showed as "must" at the fight's outcomes.** Combat outcomes now drop consumables.
7. **Flee costs were ignored.** They are now applied on the flee outcome.

Polish from the same review:
- **Codewords from other books:** a codeword set only in another book of the series is now "may" at the start, so `gate_never` no longer contradicts `flag_never_set`.
- **Mention renames** no longer write `""` over empty fields.
- **`trapped`** is reported once, where readers first get stuck.
- **Beats** only cover, and can only link, nodes in their own act.
- **Outline** controls are disabled while a save is in flight.
- **Deleting an entry** ignores its own self-mentions when counting uses.
- **The digest tier** waits for the rules to load (no double fetch).

## Tests
- **Backend: 397**
  - `test_digest.py`: diamond must/may, gate verdicts, condition guarantees, consumables, loops and unbounded depth, canonical predecessor, unreachable, characters and tier-gated choices, impossible choices proving nothing.
  - `test_validation.py`: digest rules.
  - `test_outline.py`: beats CRUD, order, undo, node deletion, cross-book rejection, problems, mentions and backlinks and renames, the digest API.
  - The tree round trip now includes beats.
  - Review regressions: once-only gains in loops, impossible shortcuts, unreachable-through-impossible, mid-fight consumables and flee cost, `unreachable_gated` and single `trapped`, beats limited to their act, and the mention index staying fresh through undo, act deletion and forced deletes.
- **Frontend unit: 54.**
- **Browser: 18** (3 consecutive full runs green). New in `e2e/lore.spec.ts`: characters ⇄ lore mentions with broken-link styling and backlinks; outline beat linking, then the inspector Digest tab (must, gate verdicts, beats, story so far).

## Decisions
- **Digest at the highest tier for validation** (every choice exists there). The inspector uses the UI tier.
- **Bare `[[key]]` is indexed against both characters and lore**, so the backlink appears wherever it resolves. The UI prefers the character.
- **Item counts and stat values aren't tracked** in the digest (and the UI says so). Stat ranges from SPEC §2.9 are deferred.

## Known issues / notes
- **Digest speed:** the fixpoint is set-based. Very large, loop-heavy books with hundreds of conditions take seconds per validation (3,000 nodes with 300 items and flags: about 8.5 s). If real books get there, switch the fact sets to bitsets or cache by content hash.
- **Shared keys:** renaming a key also rewrites bare `[[key]]` mentions when a character and a lore entry share that key.
- A bare `[[key]]` that names both a character and a lore entry shows a backlink on both.
- The inspector tab strip scrolls when all six tabs don't fit.

## Phase 7 starting points
1. **Context assembly** (SPEC §5.1) can use `digest.compute(...).nodes[id]` must/may facts, the canonical predecessor chain, act summary, linked beats, and lore from the node's location, its characters and resolved mentions.
2. **Stale tracking:** the inputs hash should include the digest facts and linked lore text.
