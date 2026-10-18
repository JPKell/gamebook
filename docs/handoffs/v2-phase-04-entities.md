# v2 Phase 4 — Enemies, items, encounters

**Status:** Complete · **Date:** 2026-10-18 · **Branch:** `v2` 

## What was built

### API
| Endpoint | Purpose |
|---|---|
| `GET /enemies/{id}/levels?level_from&level_to` | The enemy's stats at each level (1–50 levels) for every tier of the active rule system, the stats each tier is missing, and per-formula errors. |
| `GET /series/{id}/entity-problems` | Validation of the series' enemies, items and tables, independent of any book. A probe book with every entity available runs the book validator (`services/snapshot.series_entity_problems`). |
| `GET /series/{id}/item-totals` | Per item key: `total` supplied (placements, shop stock, gives, table results, loot) and `uses` (every reference). |
| `GET /series/{id}/where-used` | Now also returns `book_title` and `source_label` (the name of the enemy/table/item that holds the reference). `total_qty` uses the same supply roles as item totals (`refs.ITEM_SUPPLY_ROLES`). |

### Frontend (`frontend/src/features/entities/`)
- **`/enemies/:seriesId`** has two tabs: Enemies and Random tables. The selection is kept in `?id=` and the tab in `?tab=tables`.
- **Enemies list:** search, tags, and an error/warning badge from entity problems.
- **Enemy editor:**
  - **Details:** name, key, scope (shared or one book), default level, tags, description.
  - **Stats by level:** one `GbxField` (`enemy_formula`) per stat any tier needs, labelled with the tier that first needs it. Stray formulas are flagged "not used by any tier". Server errors show inline.
  - **Level table:** L1–10, with a tier switch that defaults to the global UI tier. Missing stats are called out, and the default level is highlighted.
  - **Difficulty vs a reference player:** win-rate sweep for L1–10, run on demand, 500 fights per level per tier (up to 3 tiers), using `LineChart`.
  - **Abilities, loot,** and **where it appears**, with links into the story.
- **Random tables editor:**
  - Dice is a `GbxField` with the `roll` context, plus a roll-range readout.
  - Result rows: range, kind (enemies/item/gold/nothing), payload and note.
  - Each row shows its chance, summed from `/gbx/check`'s exact distribution.
  - Inline coverage status: gaps ("Nothing happens on 5–6"), overlaps (the first entry wins, matching the engine), or "Every roll has exactly one result". The logic is pure and unit-tested (`coverage.ts`).
- **`/items/:seriesId`:**
  - The list is grouped by category, with `×total` per item.
  - **Editor:** category with a hint about what it means, slot (from the active rules' tier slots), value, uses (consumables), stackable and max stack.
  - **Modifiers:** stat, amount `GbxField`, and "X and up" tier limit.
  - **When used:** effects, reusing the inspector's `EffectsEditor`.
  - **Placements:** the total plus every reference.
- **Story deep link:** `/story/:bookId?node=<id>` opens and reveals the node (after the per-book store reset), then drops the param.
- **Deleting a referenced entity:** the dialog shows the reference count and deletes with `force`.
- **Shared pieces:**
  - `MasterDetail`: searchable, grouped list plus a detail pane.
  - `SeriesRedirect`: `/enemies` and `/items` open the last book's series.
  - `useSeriesVocab`: a series-level formula vocabulary with no nodes.
  - `WhereUsed`, `Panel`, `ScopeSelect`.

Encounter and shop editors in the inspector already existed from Phase 2. Enemy/table pickers there now have full managers behind them.

## Bug pass (independent review)
Seven findings, all fixed, with regression tests:
1. **Edits lost on quick clicks (data loss).** Typing in a field and then clicking Add/Remove in a list (table results, abilities, loot, modifiers) sent a second PATCH built from pre-edit props, which wiped the edit.
   - Entity saves now go through `useSaveEntity`: the cached list is updated synchronously, saves are serialised per kind, and the server is refetched only once the queue is empty (the Phase 3 pattern).
   - List edits pass a function of the latest value, and row edits pass partial patches.
   - Test: `staleEdits.test.tsx`.
2. **Overlap chances were wrong.** Chances now give each roll to the *first* covering entry, as the engine does, so they sum to at most 100%.
3. **Huge dice ranges showed a false "Every roll has exactly one result".** Coverage is now a boundary sweep (O(entries²)) with no range limit.
4. **`?node=` deep links selected the node but didn't centre it.** The initial `fitView` overrode the centring. The canvas now skips fit-on-open when a reveal is pending (checking the store and the URL). The e2e asserts the zoom.
5. **Derived views could be stale after edits elsewhere** (story, rules): where-used, item totals, entity problems and enemy levels. They now use `staleTime: 0`, so opening the page refetches. The dice check moved out of the `['entities', series]` prefix so entity saves don't re-check it.
6. **No formula fields without an active rule system** (the levels endpoint returns 422). The panel now falls back to the rule vocabulary's stats, which are also shown while loading.
7. **Item totals counted shop `stock: 0` as 1, and unlimited stock as 1.**
   - `refs.supply()` now returns `None` for unlimited stock. Totals expose `unlimited`, and the UI shows `×N+` with an explanation.
   - Shop stock 0 now adds nothing.

Polish from the same review:
- Blank formulas count as missing.
- The level table extends to the default level (up to 50).
- The difficulty curve says when the formulas changed since it ran.
- Switching away from equipment clears the slot, and unknown categories sort last.
- Delete waits for the reference count.
- Lists show loading and "No matches".
- Status icons have `role="img"`, and untitled nodes have a link name.
- The view switch is a radiogroup.
- Where-used source names come from one query per type instead of one per row.
- New table rows start at the first gap.

## Tests
- **Backend:** 329 (new: `tests/api/test_entities_phase4.py`, covering levels per tier, missing, blank and broken formulas, entity problems, enriched where-used, item totals, and shop stock 0 and unlimited).
- **Frontend unit:** 51 (new: `coverage.test.ts`, covering first-match chances and huge ranges; `staleEdits.test.tsx`). The AppShell nav test now targets Lore, because Enemies is built.
- **Browser:** 13. New in `e2e/entities.spec.ts`:
  - create an enemy, write a formula and read the level table across a reload
  - table gaps, overlaps and chances, fixed to full coverage
  - item total, then a where-used link into the story that opens and centres the node
- Four consecutive full browser runs were green.

## Decisions
- **Validating entities outside a book uses a probe book** rather than a second validator, so book and series problems can't drift.
- **Item totals count supply, not mentions.** Unlimited shop stock is flagged (`unlimited`) rather than counted (SPEC §2.12).
- **The difficulty sweep runs only on demand** (it's about 15k fights), so selecting an enemy stays instant.

## Known issues / notes
- Validation reports table gaps as an error, and the editor shows the same gap inline as a warning-styled status, so the message appears twice.
- In entity rows, `GbxField` is about 4px shorter than native inputs.
- Stat-key renames still don't rewrite enemy formulas or item modifiers (carried over from Phase 3).
- `EffectsEditor` (item use effects, and the story inspector) still builds its next list from props. It's safe because entity saves now update the cache synchronously before the next click, but it isn't functional like the other list editors.
- Enemy formulas can produce integers above 2^53, which lose precision in the browser. No clamp yet.
- The Enemies/Random tables switch and the tier picker have no arrow-key navigation.

## Phase 5 starting points
1. Player view on top of `core.engine.Game` (Phase 3) via the bundle endpoint. TS engine parity comes later (golden traces exist).
2. Bots: policies over `Game.actions()`. Batch runs as Jobs with SSE progress.
3. The playtest dashboard can reuse `components/charts` and the `MasterDetail`/`Panel` patterns.
