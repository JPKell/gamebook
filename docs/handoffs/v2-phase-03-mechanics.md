# v2 Phase 3 — Mechanics designer & engine

**Status:** Complete · **Date:** 2026-10-18 · **Branch:** `v2` (uncommitted at time of writing)

## What was built

### Engine (`backend/src/gamebook/core/engine/`, pure, mypy --strict)
| Module | Purpose |
|---|---|
| `game.py` | `Game(book, tier, seed)`: character creation (rolled or fixed stats, classes grant skills), `actions()`/`available()`/`step()`, once-only effects, stat clamping (min, max, `max_is_initial`), effective stats with item modifiers (equipment while equipped, by tier), text-variant selection, roll/test/combat choices, found items, shops (stock, money, selling at the shop's rate), consumables, equip/unequip, defeat (authored endings win), `stuck` detection. Content errors become `error` events. |
| `combat.py` | The SPEC §2.4 procedure: sequential or simultaneous, ties, damage hooks with `natural`, stalemate cap; shared with the lab. |
| `lab.py` | `simulate()` (Monte Carlo fights, rolled or fixed player, ≤20k runs) and `level_sweep()`; distributions with mean, p50 and p90. |
| `bundle.py` | `BookSnapshot` ⇄ JSON game bundle (exact round trip). |
| `trace.py` | Golden traces: `record`/`replay`; policies `first_available`, `rotating`. |
| `events.py`, `state.py`, `env.py` | Plain-data events, actions and state; gbx Env adapters; compiled-expression caches. |

### gbx additions
- **`compiler.py`**: closure compilation, ints with exact fractions only when needed. It's equivalent to the evaluator (Hypothesis test plus edge cases) and about 2–3× faster (ADR 0007).
- **`SeededRng` is now PCG32** with unbiased bounded rolls and pinned reference vectors, for TypeScript parity (ADR 0006).

### API
- `GET /rule-systems/{id}/tiers/{tier}`: merged tier with provenance (`introduced`/`origin` per definition, combat field origins, hook origins).
- `GET /rule-systems/{id}/problems`.
- `POST /series/{id}/combat-lab`: series enemies at a level, or ad-hoc stats; returns win rate and round/damage distributions.
- `POST /series/{id}/combat-lab/sweep`: win rate by level, with work bounded to levels × runs ≤ 30,000.
- `POST /gbx/check` accepts `rule_system_id` to check against a draft system.

### Mechanics designer (`frontend/src/features/mechanics/`)
- `/mechanics/:seriesId?rs=&tier=&view=` with series and rule-system pickers. The active/draft badge and system actions: make active, rename, duplicate as a draft, new from template, delete.
- **Tier tabs** with "+Parent" hints, plus Add tier, which inherits from the last tier.
- **Rules view** sections:
  - **Tier:** name, parent, description, delete (protected while other tiers inherit from it).
  - **Stats & resources, Tests, Skills, Classes:** inherited rows are dashed with a "from X" chip and an **Override** button; own rows edit inline, and overrides can **Revert**.
  - **Equipment slots.**
  - **Combat:** each field shows what it inherits; set it here or clear to inherit; damage rules show inherited ones read-only.
  - **Rules chapter text.**
- All formula fields use `GbxField` against the edited tier and rule system. Effects reuse the inspector's `EffectsEditor`.
- Saves are optimistic and serialised per rule system (TanStack mutation scope).
- **Rule problems banner**: links jump to the offending tier.
- **Combat lab view**:
  - Setup: enemy, level and count, fights, rolled or fixed player, seed.
  - Results: stat tiles (win rate as the headline), rounds and damage histograms, table views.
  - **Difficulty curve**: win rate by level, optionally comparing up to 3 tiers, with a legend, direct end labels (collision-avoided), a crosshair tooltip and a table view.
- **Charts** (`components/charts/`) follow the dataviz skill: validated 3-slot palette on this app's light and dark surfaces, single y-axis, thin marks, hover plus table view.

## Bug pass (independent review)
The review confirmed 11 bugs, all fixed, with regression tests in `backend/tests/core/test_engine_regressions.py` (plus frontend tests):
1. An item bonus on the damage stat made the player unkillable. Defeat is now judged on the base stat everywhere.
2. "Stuck" was declared before the reader could take an item or shop. It now means nothing at all can be done, and is re-checked after every step.
3. Content errors in combat rules (unparseable, or a runtime error like `/ 0`) crashed the engine, and the lab returned 500. They now become `error` events (game) or 422s (lab and sweep).
4. Wrong argument counts (`floor()`, `clamp(1)`) raised `IndexError`. They are now `GbxEvalError`s in both the evaluator and the compiler.
5. The compiler drew dice for `clamp` arguments in a different order from the evaluator. Both now use source order, which keeps TS parity safe.
6. `actions()`/`available()` appended error events. Queries are now silent, and broken conditions are reported once on arrival.
7. Sell actions were offered without a currency stat, and crashed.
8. Buying at `max_stack` took money and gave nothing. That buy is now disabled with "Can't carry more".
9. `min: null` became 0 on save and in bundles. Rule systems are now stored and bundled without `exclude_none`.
10. Rapid Mechanics edits could clobber each other through an intermediate refetch. The server is now refetched only once the save queue is empty, and errors resync from the server.
    - A guard test asserts no refetch happens between queued saves.
    - In this TanStack version the original clobbering didn't reproduce in a test harness, so treat this fix as defensive.
11. The lab had unbounded CPU per request (up to about 30 min). There's now a work budget of 1M fighter-rounds per request (about 5 s worst case) with `truncated` results, and at most 10 enemies per fight.

Also fixed from the review's "plausible" list:
- A consumable that defeats you mid-fight now ends the game.
- Key renames in the designer can't collide, and override keys are locked.
- Damage-rule rows have stable React keys.
- Lab defaults come from the tier's own stats.
- Histograms bin wide ranges, capped at 60 bars.
- The dice history no longer grows across a whole game.

## Tests
- **Backend**: 321 (engine: 47 incl. Hypothesis determinism/bounds and 6 golden traces; 16 review regressions; compiler ≡ evaluator; PCG vectors and uniformity; mechanics API).
- **Frontend unit**: 44.
- **Browser (Playwright)**: 10, including override/revert across reload, the lab and curve, and add tier. 5 consecutive full runs at 4 workers were green.
- The starter template now carries rules-chapter text per tier, so the golden traces were regenerated deliberately.

## Decisions
- Portable PCG32 dice and versioned bundle/trace formats now, before anything depends on Python's RNG (ADR 0006).
- Compiled gbx in the engine; the evaluator remains the reference (ADR 0007).
- Authored ending nodes take precedence over stat defeat on entry.
- Selling equipment unequips it; currency is the first `resource` stat of the tier.
- Validation errors from model validators were returning 500 (exception objects in `ctx`). Fixed globally with `jsonable_encoder`. This also affected Phase 1 endpoints such as `ChoiceCreate`.

## Known issues / notes
- Stat keys can be renamed in the designer, but book content referring to the old key isn't rewritten yet (shows as validation errors). Rename cascades for stats and tiers are a later item.
- The lab simulates fights only. Whole-book bot runs are Phase 5.
- Lab throughput: about 10k basic fights/s and about 3k advanced fights/s per request thread.

## Phase 4 starting points
1. Enemy manager: per-tier formula editor with live L1–10 table (reuse `TierView` + `enemy_stats`), "simulate vs reference build" via `POST /combat-lab`.
2. Item manager: modifiers per tier, use effects, placements from `GET /series/{id}/where-used`.
3. Random tables editor with coverage (validation already exists) and probabilities (`gbx.distribution`).
