# v2 Phase 1 — Domain model, gbx, authoring API

**Status:** Complete · **Date:** 2026-10-18 · **Branch:** `v2` (uncommitted at time of writing)

## What was built

### Pure core (`backend/src/gamebook/core/`, mypy --strict)
| Module | Purpose |
|---|---|
| `gbx/` | The expression language: `lexer` → Pratt `parser` → immutable `ast` (JSON round-trip) → `checker` (names, types, dice/context rules, tier scope, integrality, printability) → `evaluator` (exact fractions, seeded `SeededRng` recording every roll, `SimpleEnv`) → `english` (print phrasing for conditions/numbers) · `source` (canonical printer) · `analysis` (value ranges, exact dice distributions) · `references` (extract keys; span-preserving rename). |
| `gbx/scope.py` | `Scope` + standard `Context`s (condition, amount, roll, test_roll, test_success, enemy_formula, stat_initial, combat_attack, combat_damage) built from `ScopeInputs`. |
| `keys.py` | Key rules (`^[A-Za-z][A-Za-z0-9_]{0,63}$`, not dice-like, not reserved), `slugify`, `unique_key`. |
| `effects.py` | Discriminated-union `Effect` (modify, set, give, take, equip, set_flag, clear_flag, learn) with `once`/`min_tier`/`print_text`; refs, rename, English. |
| `rules/` | `RuleSystemDef` → tiers with stats/tests/skills/classes/slots/combat hooks; `effective_tier` merges the parent chain (hooks accumulate); `default_rule_system()` starter (Basic FF-style, Medium armour+slots, Advanced classes/skills/crits). |
| `model.py` | Frozen `BookSnapshot` (acts, nodes, variants, choices/outcomes, encounters, placements, shop, entities, rules, series flags) — input to analysis now, the engine later. |
| `analysis/` | `validate_book` (structure, act boundaries, reachability, endings, dead ends, roll/table coverage, outcome keys per kind, tests/combat wiring, expressions per tier with "only exists from tier X" warnings, effects, entities, enemy formulas per tier, codewords never set, section pins) and `validate_rule_system`. |

### Persistence (`db/models/`, migration `0002`)
Series, RuleSystem, Book, Act, Node, NodeCharacter, TextVariant, Choice, ChoiceOutcome, Encounter, EncounterEnemy, NodeItem, ShopItem, Enemy, Item, RandomTable, Character, LoreEntry, RefIndex. Entities always carry `series_id` (+ `book_id` when book-specific); keys unique per series. Row relations are FKs; references inside expressions/JSON are keys.

### Services (`services/`) and schemas (`schemas/`)
- `series`, `books` (new books get "Act 1" + a "start" node), `nodes` (nodes, variants, choices with per-kind default outcomes, encounters, placements, shop, layout, duplicate-with-remap), `entities` (generic CRUD for enemy/item/table/character/lore with delete guard + `force`), `refs` (RefIndex extract/reindex/rebuild, where-used, flag usage, **key rename across all references**), `snapshot` (DB → `BookSnapshot`, validation), `gbx_tools` (editor check), `transfer` (export/import).
- Schemas live in `gamebook/schemas/` so services never import from `api/`.
- Service errors (`ConflictError` 409, `InvalidError` 422) carry `details` (e.g. `field`, `ref_count`) into the error envelope.

### API (all under `/api`, browse at `/docs`)
Series & rule systems · books, acts (reorder, delete with `force`) · `GET /books/{id}/graph` (everything the canvas needs) · `GET /books/{id}/problems` · `PUT /books/{id}/layout` · `POST /books/{id}/duplicate` · nodes, variants, choices (+order), encounters, `PUT /nodes/{id}/items`, `PUT /nodes/{id}/shop` · enemies/items/tables/characters/lore (list filtered by `book_id`) · `GET /series/{id}/where-used?target_type=&key=` (with item `total_qty`) · `GET /series/{id}/flags`, `POST …/flags/rename` · `POST /series/{id}/reindex` · `POST /gbx/check` (diagnostics with spans, normalised source, English, range, odds) · `GET /series/{id}/export.zip`, `POST /import[?replace=true]` (zip body).

### Git tree export/import (`export/tree.py`)
Deterministic YAML/Markdown tree (layout in the module docstring and SPEC §6.1): no timestamps, empty values omitted, keys for cross references, ids preserved. `gamebook export <series-key> <dir>` / `gamebook import <dir> [--replace]`. Import is transactional and rebuilds the RefIndex. Writing a tree only replaces managed paths (your README/.git are untouched).

## Tests — 227 backend after the bug pass (200 before it) (+14 frontend, 3 e2e unchanged)
- gbx: parse/print and JSON round-trips, parser never crashes, evaluation total and within computed ranges (Hypothesis), errors with spans, contexts, rename, English.
- Rules: tier merge, chains, rule-system validation. Validation: every rule in SPEC §7 that exists so far.
- API: full authoring flows, cross-book/series rejection, deletes and SET NULL semantics, where-used + totals, key renames (items/enemies/nodes/flags) rewriting conditions, effects, loot, tables and visits(); **incremental RefIndex == full rebuild**; export → import → export byte-identical, graph/problems/entities identical after import; conflicts, malformed input, rollback on failed import; CLI.
- Migrations: drift check, downgrade to base and re-upgrade.

## Decisions made during the phase
- **Keys use `_`, not `-`** (gbx would read `-` as minus). SPEC updated.
- **Rule-system schema + tier merge moved into Phase 1** (expression checking needs per-tier stats). Phase 3 now focuses on the engine, designer UI and combat lab.
- **Numbers are exact fractions**; integer contexts round down; checker warns on unrounded `/`.
- **Bare stat names** (`GOLD`) mean the player's stat in player contexts.
- **Dice are not allowed in conditions** (use a roll choice) **or enemy formulas**.
- Things only defined in a higher tier are a *warning* suggesting `min_tier`, not an error.
- RefIndex matches targets **by key** (references can precede the entity they name).
- API responses include explicit `null`s for optional effect fields (keeps generated TS types precise); stored JSON omits them.
- SQLAlchemy 2.1: `Result.tuples()` is deprecated — rows unpack directly.

## Bug pass (independent review)
An independent review reproduced 12 bugs; all are fixed with one regression test each in
`tests/api/test_review_regressions.py`:
node-key renames leaked into other books · export dropped `once: false` inside effects ·
import accepted path-traversal keys / unknown lore types (plus `write_tree` containment and
symlink refusal, zip size limits) · enemies linked to book-scoped lore failed to re-import ·
`enemy.lore_entry_id` unvalidated (and now indexed) · nullable entity fields couldn't be
cleared · book-scoped entities usable from other books · roll/table coverage was O(range)
(now an endpoint sweep) · dice distributions unbounded (now capped by outcome span, integer
convolution) · deep expressions caused RecursionError (depth limits incl. total AST depth) ·
English rendered `true` as "never" · RefIndex stale after node create/rename and rule-system
changes. Also: `key: null` in PATCH no longer re-derives keys, malformed imports are 422 not
500, books with no endings get a `no_endings` warning.

## Known issues / notes
- The UI doesn't use any of this yet (Phase 2). The Problems panel still shows a stub.
- `visits()` is flagged "info: unprintable" until the print compiler (Phase 10) gives it a strategy.
- Effects inside rule-system tests (`after`) and `flee_cost` aren't in the RefIndex yet; stat/tier renames (a Phase 3 rule-system editing concern) aren't implemented.
- Undo needs "re-create with the same id" support; add when the Phase 2 command stack lands.

## Phase 2 starting points
1. `GET /books/{id}/graph` + React Flow; act frames from `acts`, edges from `choices[].outcomes[]` (style by `kind`, dashed when `condition`).
2. Inspector tabs map 1:1 to the node/choice/variant/encounter endpoints; use `POST /gbx/check` for live diagnostics and English in the CodeMirror gbx field.
3. Problems panel: `GET /books/{id}/problems` (counts + navigable rows with node/choice ids).
4. Mutations → TanStack Query invalidation of `["graph", bookId]` and `["problems", bookId]`.
5. Series/book switcher in the breadcrumb (`GET /series`, `GET /series/{id}`).
