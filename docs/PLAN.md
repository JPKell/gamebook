# Gamebook Studio — v2 Build Plan

> Implements `docs/SPEC.md`. Supersedes `docs/archive/v1-plan.md`.
> Priority (from interview): **authoring core first**, then mechanics & play,
> then lore + LLM writing, then LLM playtesting, then print/EPUB/player.

## What carries over from v1

| Keep (as concepts / reference) | Replace |
|---|---|
| Series → Book → Act → Node → Choice hierarchy | JSON-string ID lists on nodes → real tables + RefIndex |
| Shared (series) vs book-scoped entities | Duplicate choice storage (column + table) |
| Beat notes vs. generated prose separation | Mixed camel/snake naming, no Pydantic schemas |
| Inference client retry/backoff logic (`app/services/inference.py`) | Single 1,400-line `app.js` → React/TS feature modules |
| Validation rule ideas | Modals-for-everything UX → inspector panels |
| Phase → bug pass → tests → handoff workflow | Ad-hoc preview combat → shared rules engine |

v1 is tagged `v1-prototype` and its code removed in Phase 0; nothing is migrated.

## Working agreement (every phase)

1. Read the previous handoff in `docs/handoffs/`.
2. Build the phase; keep `core/` pure and typed.
3. Bug pass + tests (unit, property, API, and e2e for new UI flows).
4. Update SPEC.md if a decision changed; add an ADR for any architectural choice.
5. Write `docs/handoffs/v2-phase-NN-<name>.md` and update the index in `docs/handoffs/README.md` (what was built, decisions, known issues, next steps).
6. **Definition of done:** CI green (ruff, mypy, pytest, tsc, vitest, playwright), the phase
   demo script works end-to-end in the running app.

---

## Phase 0 — Foundations ✅ (2026-10-17, see `docs/handoffs/v2-phase-00-foundations.md`)

- Tag `v1-prototype`; remove v1 code; new `backend/` (uv, src layout) and `frontend/` (Vite React TS).
- FastAPI app factory, settings (pydantic-settings + `config.yaml`), structured logging.
- SQLite engine (WAL, FK on), Alembic baseline, UUIDv7 ids, base repository pattern.
- OpenAPI → TS client generation script; `make dev` runs both with proxy.
- Frontend shell: nav rail, routing, theme, command palette stub, Problems panel stub.
- Tooling: ruff, mypy, pytest, vitest, playwright, pre-commit, GitHub Actions CI.
- ADRs: 001 stack, 002 pure core, 003 gbx language, 004 SQLite + git tree.

**Demo:** app boots, empty shell navigates, CI green.

## Phase 1 — Domain model, gbx, authoring API ✅ (2026-10-18, see `docs/handoffs/v2-phase-01-domain.md`)

- **gbx v1**: lexer, Pratt parser, AST (JSON), type checker with contexts, evaluator,
  dice (seeded), print renderer. Hypothesis tests (parse ↔ print round-trip, evaluator totality).
- DB models: Series, StyleGuide, Book, Act, Node, TextVariant, Choice, Outcome, Effects,
  Enemy, Item, RandomTable, Encounter, Shop, Character, LoreEntry (tables now; UIs later).
- **RefIndex** maintenance on every write; where-used + key-rename refactor endpoints.
- Authoring API with Pydantic schemas: CRUD + graph ops (create node+link, move, bulk
  layout save, duplicate subgraph).
- Validation engine v1 (structural rules from SPEC §7, gbx errors).
- **Git tree export/import** (round-trip test) — your writing is safely in git from here on.

**Demo:** build a small book via `/docs` OpenAPI, export to tree, wipe DB, import, identical.

## Phase 2 — Story graph editor ✅ (2026-10-18, see `docs/handoffs/v2-phase-02-graph-editor.md`)

- React Flow canvas: act group frames, node cards with badges, typed edge styles, minimap,
  ELK auto-layout per act, search & filters.
- Drag-to-link, drop-to-create, multi-select, copy/paste, keyboard navigation.
- Inspector panel tabs: Beat, Choices (all resolution kinds, gbx editor with autocomplete &
  live print rendering), Effects, Text variants, Lore links (pickers).
- Problems panel wired to validation; click-to-navigate; validation overlay.
- Autosave on every edit (optimistic TanStack mutations); undo/redo via **server-side book
  snapshots** (see ADR 0005) instead of client inverse operations; named checkpoints (SQLite backup).
- Series/book/act management screens; style guide editor.

**Demo:** author a 3-act, ~30-node book with gated, roll and combat choices entirely in the UI.

## Phase 3 — Mechanics designer & engine ✅ (2026-10-18, see `docs/handoffs/v2-phase-03-mechanics.md`)

- ~~RuleSystem schema, tier inheritance/merge, validation of tier definitions~~ (pulled into
  Phase 1, because expression checking needs per-tier stats; a starter template is seeded).
- Engine: GameState, character creation, `available_actions`, `step`, effects, tests,
  combat procedure with hooks, shops, equipment/slots, consumables, `once` semantics,
  visits; full event log; seeded RNG.
- Golden-trace format + first traces (for future TS parity).
- Mechanics designer UI: tier tabs, inherited/overridden display, all sections.
- **Combat lab** (10k-fight Monte Carlo, level sweeps, charts).
- Refine the starter rule system template (FF-style basic → armour medium → classes/crits
  advanced) once the engine can play it.

**Demo:** define three tiers, tune a fight in the lab, see difficulty curves shift.

## Phase 4 — Enemies, items, encounters ✅ (2026-10-18, see `docs/handoffs/v2-phase-04-entities.md`)

- Enemy manager: table, per-tier formula editor, live level table + chart, where-used,
  "simulate vs. reference build".
- Item manager: categories, modifiers per tier, use effects, computed placements & totals.
- Random tables editor (coverage/overlap check, probabilities); encounter & shop editors in
  the inspector.
- Validation additions: missing tier formulas, table coverage, item references.

**Demo:** enemy page shows L1–10 stats for each tier and every node using it; item page
shows correct total quantity across nodes, tables and shops.

## Phase 5 — In-app player & bot simulation ✅ (2026-10-18, see `docs/handoffs/v2-phase-05-playtest.md`)

- Player view: tier select, character creation, prose/beat-notes fallback, rendered
  mechanics blocks, adventure sheet, dice log, back/restart. **Debug drawer**: jump to node,
  edit state, force rolls.
- Bots: random, greedy, cautious, explorer, completionist; batch runner as background Job
  (SSE progress); coverage walker.
- Playtest dashboard v1: outcomes, act funnel, deadliest nodes/enemies, item lift, endings,
  coverage; canvas heat overlay; batch compare; run replay viewer.
- Content hash + rule-system snapshot stored per batch.

**Demo:** run 5,000 bot games per tier in seconds; find and fix an overly deadly node; compare batches.

## Phase 6 — Lore, outline, state digest ✅ (2026-10-18, see `docs/handoffs/v2-phase-06-lore-digest.md`)

- Lore wiki: characters (relationships, appearances), locations, factions, history,
  glossary; `[[key]]` mentions + backlinks.
- Act outline & story beats linked to nodes; beat coverage warnings.
- **State digest** dataflow analysis; shown in inspector; new validation rules
  (never/always-satisfiable gates, softlock loops, can't-reach-ending).
- Canonical predecessor auto-selection + override.

**Demo:** node inspector shows "must have: RAVEN; may have: Silver Key"; a gate flagged
as unsatisfiable.

## Phase 7 — LLM infrastructure & prose pipeline ✅ (2026-10-18, see `docs/handoffs/v2-phase-07-prose.md`)

- Provider profiles (local / OpenAI / OpenRouter), model registry, pricing, concurrency.
- Prompt template store (versioned, editable), LLMCall log browser, cost tracking.
- Context assembler with token budgeting (SPEC §5.1); rolling node summaries.
- **Writer → Critic → Editor** loop with configurable models, threshold, iterations.
- Prose versions, review UI (diff, critique trail, approve/edit/reject/regenerate),
  stale propagation, writing queue, "generate act in canonical order" batch job.
- Tests use a fake provider with scripted responses; one opt-in live smoke test.

**Demo:** generate Act 1 prose, review with critique trail, approve, edit an upstream beat
and watch downstream nodes go stale.

## Phase 8 — LLM authoring assists ✅ (2026-10-18, see `docs/handoffs/v2-phase-08-assists.md`)

- Consistency checker (node/act/book) → issues in Problems panel with quotes.
- Beat/branch suggester → draft subgraph overlay, accept per node/choice.
- Lore extractor → draft lore entries for review.

## Phase 9 — LLM players ✅ (2026-10-18, see `docs/handoffs/v2-phase-09-llm-players.md`)

- Reader-view renderer as LLM input; JSON action protocol; personas; rolling memory.
- LLM batches in the playtest system (budget caps, concurrency, resumable).
- Dashboard additions: confusion notes grouped by node, model vs. model, LLM vs. bot
  comparisons; reasoning in the run viewer.

**Demo:** three models play Act 1–3 on Medium; dashboard shows where they got confused.

## Phase 10 — Artwork, maps & appendices

- **Asset library** (SPEC §2.13):
  - content-addressed storage under the data dir, Pillow thumbnails, dedupe by hash
  - alt text, caption, credit and licence; tags
  - where-used through the RefIndex; delete guard; checkpoint-safe garbage collection
  - git export of `assets/` + `assets.yaml`
- **Node artwork:**
  - several illustrations per node, optionally per text variant
  - inspector Art tab, plus a thumbnail on the canvas card and in the in-app player
- **Print layout controls per placement:**
  - size: full page with optional bleed, full width, half, third, vignette, or custom mm / %;
    maximum height
  - position: before or after the text, after paragraph N, own page (recto/verso), facing page
  - alignment and text wrap with a gutter
  - crop by focal point and aspect ratio
  - keep with the section
  - live effective-DPI check

  Digital display has its own settings.
- **Full-page art:** act openers (recto by default), front/back cover, frontispiece, title page.
  The preview shows trim, bleed and safe area.
- **Portraits and images** for characters, enemies, items and lore entries.
- **Commissioning tracker:** placeholders with an art brief and status (needed → sketch →
  final); shot-list export (Markdown/CSV) for illustrators.
- **Maps:** a map entity over an image asset, with markers linked to nodes or lore locations
  and optional codeword reveal conditions; map editor; interactive map in the in-app player.
- **Appendix builder** (SPEC §2.14), per book; every appendix is tier-aware with spoiler
  options. The kinds are:
  - bestiary (stat blocks at the levels used, or level tables)
  - adventure/stat sheet generated from the tier's stats, slots and codewords
  - item catalogue / inventory
  - rules quick reference
  - dramatis personae
  - glossary
  - maps
  - custom Markdown pages

  Preview uses the HTML templates that Print will reuse. In the player, appendices appear as
  a **Codex** whose bestiary and item entries unlock as they're met.
- **Validation:** low DPI for the printed size, bleed coverage, placeholders and missing alt
  text, broken map markers, unused assets.

**Demo:**
1. Upload ten images.
2. Place a half-width wrapped vignette in a node and watch its DPI turn amber when you
   enlarge it.
3. Add a full-page act opener and a map with clickable markers.
4. Preview the Medium-tier bestiary and the adventure sheet.
5. Export the shot list of art still needed.

## Phase 11 — Print & EPUB

- Section numbering (seeded shuffle, pins, stable map, reshuffle).
- Print compiler: variants → split sections, visits → tick boxes/codewords, gated choice
  phrasing, per-tier mechanics blocks.
- HTML/CSS templates → PDF (WeasyPrint): front matter, rules chapter, adventure sheet,
  sections, back-matter appendices; EPUB with internal links and embedded art.
- Artwork layout honours the Phase 10 print controls:
  - full-page art and bleeds, recto act openers, wrap and keep-with rules
  - layout warnings when an illustration can't stay with its section
  - a pre-flight DPI and bleed report
- Proofing view: section-by-section preview; "verify printed book" bot that plays the
  *compiled* sections to prove compilation preserved the game.

## Phase 12 — Standalone digital player

- Game bundle export (versioned schema), including screen-sized artwork, maps and the codex.
- TS port of gbx + engine; golden-trace parity suite in CI.
- Static web/PWA reader app with save slots.

## Later / deferred

Cross-book carry-over (CharacterSnapshot + import policy), combined vs. per-tier print
editions, mobile wrapper, multi-user.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Rules too expressive to print | Print renderer required for every gbx/effect construct; validation flags the rest; Phase 11 "verify printed book" bot |
| Python ↔ TS engine drift | Golden traces from Phase 3; parity suite gates Phase 12 |
| LLM cost / slowness | Bots carry balance testing; budgets per batch; caching by inputs hash; local models first |
| Prose contradicting branching state | State digest in prompt + critic path-validity score + consistency checker |
| Scope creep | Each phase has a demo; phases 8–12 can be reordered without blocking authoring |
| Data loss | Immediate persistence, checkpoints, git tree export from Phase 1 |
| Art files outside SQLite (backups, checkpoints) | Content-addressed files never deleted while any row or checkpoint references them; included in git export and checkpoints' manifests |
| Print art looks wrong only at the printer | Physical-size DPI check, trim/bleed preview, pre-flight report before PDF export |
