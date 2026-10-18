# v2 Phase 5 — In-app player & bot simulation

**Status:** Complete · **Date:** 2026-10-18 · **Branch:** `v2`

## What was built

### Engine & simulation (pure core)
- **`Game.clone(seed=None)`:** an independent copy that shares the immutable book.
- **Debug hooks:** `debug_jump(node_id)`, `debug_set(stats, items, flags)` and `force_roll(total)`.
  - Forced totals apply to the next choice, test, table or stat roll, never to combat rounds.
  - Each hook logs a `debug` event.
- **`engine/narrate.py`:** plain-English lines for every event type (dice faces, effects, tests, tables, combat rounds, endings, content errors).
- **`core/sim/bots.py`:** five bots that pick an index into `available()`.
  - **Bot types:** random; greedy (takes and buys, equips into empty slots); cautious (prefers plain choices, heals below 50%, flees below 30%); explorer (least-visited targets); completionist (everything, plus untried choices).
  - Bots never swap equipment, so they can't loop forever.
  - Each bot has its own RNG (`random.Random(f"{bot}:{seed}")`).
- **`core/sim/batch.py`:**
  - `play_run` returns a `RunRecord`: picks, outcome, ending and last node, death cause, and errors.
  - `replay_run` rebuilds a stored run.
  - `summarize` computes the dashboard numbers (SPEC §2.10).
- **`core/sim/walker.py`:** the bounded coverage walk (BFS over situations, sampled dice, fights as one move, money capped at the highest shop price). It reports progress.

### Jobs & storage
- **Migration 0004:** tables `job`, `playtest_batch` and `playtest_run`.
- **`jobs/runner.py`:**
  - One worker thread, with cancellation checked between chunks.
  - In-memory tracking of active jobs, so shutdown needs no database.
  - `recover()` on startup fails jobs left running by a crash; `services.playtest.recover` does the same for their batches.
- **`services/simpool.py`:** a `spawn` process pool (setting `sim_processes`: 0 means one per core, 1 means in-process). Workers cache decoded bundles by hash.
- **Batch storage:** each batch stores its bundle and content hash; runs store pick indices (ADR 0008).

### API
| Endpoint | Purpose |
|---|---|
| `POST /books/{id}/play` | The stateless player: replays `{tier, seed, character_class, fixed_stats, inputs[]}`. Inputs are `action` / `jump` / `set` / `force`. It stops at the first input that no longer applies (`applied`, `error`). |
| `GET /playtest/bots` | Bot names and descriptions. |
| `POST/GET /books/{id}/batches`, `GET/DELETE /batches/{id}` | Start, list, read and delete batches. The detail includes the summary, the job, the bundle's names, and `stale`. |
| `GET /batches/{id}/runs?outcome&offset&limit` | Paged runs. |
| `GET /batches/{id}/runs/{index}/replay?upto=` | A run replayed on its own bundle, after N steps. |
| `POST /books/{id}/coverage` | The coverage walk as a job; the result is on the job. |
| `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, `GET /jobs/{id}/events` | Job state, cancel, and SSE progress. |

### Frontend (`frontend/src/features/playtest/`)
- **`/playtest/:bookId`** has three views: Bot batches, Play and Coverage.
- **Player:**
  - Setup: tier, class, and seed ("same seed, same dice"). Back, Restart and New character.
  - The scene shows act, title, variant, and beat notes (there's no prose yet), plus "what happened" mechanics lines and an ending banner.
  - Combat panel, choice list with disabled reasons, item and shop buttons.
  - Adventure sheet (stats with max and item bonus, class, skills, inventory with equipped badges, codewords) and a dice log.
  - **Debug drawer:** jump to a node, force the next roll, set stats, toggle codewords, set item counts.
  - The session survives reloads (localStorage). A "book changed" banner offers to continue from the last valid move.
- **Batches:**
  - New-batch form: tier, bot with its description, runs, first seed, max steps, label.
  - Live progress bars over SSE, stop, delete, and a stale marker.
- **Dashboard:**
  - Headline tiles.
  - Bar lists for outcomes, act funnel and endings (`components/charts/BarList`).
  - Tables: deadliest nodes (with the death rate there), enemies, and item win-rate lift.
  - Never-visited nodes and choice coverage, plus content-error samples.
  - A paged run browser with **Replay**: step slider, first/prev/next/last, the bot's next choice, and the sheet.
- **Compare:** pick a second batch for side-by-side metrics, outcomes and act reach, with changes shown as ▲/▼ percentage points.
- **Heat overlay:** `/story/:bookId?heat=<batch>` adds a visit-share bar, "never visited" and death counts to every node card, with a banner linking back to the dashboard.
- **Coverage view:** walk the book per tier with live progress. Shows reachable count, a truncation warning, unreachable nodes (linked), and endings reached.

## Bug pass (independent review)
Eleven findings, all fixed; most have regression tests:
1. **The coverage walker never explored fleeing** (fights were always fought to the end). Fights now stay open as a state, so attack and flee are both explored. Test: flee-only content.
2. **The walker ignored `visits()`, item use, selling and once-only effects.** The state signature now includes:
   - visit counts of nodes that conditions mention, capped at 4
   - once-only pickups and effects already fired
   - the open fight

   `use` and `sell` are now explored. The default limit rose to 20k situations. Test: visit-gated content.
3. **A process pool with a dead worker was reused forever.** It is now replaced when broken (`tests/test_simpool.py`).
4. **A batch could look "running" after its job ended.** Owners are now updated before the job turns terminal. The client falls back to polling if SSE fails (`jobStream.test.tsx`).
5. **The player could get stuck on a class from another tier.** Changing tier or making a new character resets the class, and errors offer "Reset session".
6. **Batch size was unbounded.** `runs × max_steps` is capped at 2M, and `seed_base + runs` must fit in 31 bits.
7. **Death causes blamed earlier, survived fights**, and the alphabetically first foe. Deaths are now blamed only on a fight lost in the same step, and on the enemy that landed the last blow. Test: observer unit test.
8. **Replay returned 500 on a mismatched pick.** It now returns 409 with an explanation.
9. **The SSE endpoint polled the DB on the event loop.** Polls now run in the threadpool, streams are capped at 15 minutes, and a deleted job ends the stream.
10. **`debug_set` accepted unknown stats and items** (phantom state). It now rejects them, and item counts respect max stack.
11. **Double-clicking a choice showed a false "book changed" banner.** Actions are now disabled while a move replays.

Polish from the same review:
- Deleting a batch also deletes its job, and cancel only tracks active jobs.
- Engine exceptions now fail one run, not the whole batch.
- `node_visits` keys are sorted.
- Player seeds are clamped.
- The heat overlay ignores batches from other books and says when it's stale.
- "What happened" covers everything since the last real move, so a trailing debug input no longer hides it.
- The replay slider defers requests and announces the step.
- Compare deltas have screen-reader text.
- Coverage can be stopped.
- Job startup recovery only commits when something changed.

## Tests
- **Backend:** 375.
  - `tests/core/test_sim.py`: every bot × tier finishes and replays exactly; determinism; replay detecting a changed book; summary consistency; explorer coverage ≥ random; the walker finds bought-key content but not impossible or tier-gated content, and is bounded; clone independence; debug hooks; every event narrates.
  - `tests/api/test_playtest.py`: player start/step/fight/debug/changed book/validation; batches (summary, runs, replay, stale, delete); determinism; validation and size caps; cancel ordering; SSE stream; coverage job; the real process pool; restart recovery; debug key validation.
  - `tests/test_simpool.py`: a broken pool is replaced.
- **Frontend unit:** 52 (new: SSE fallback).
- **Browser:** 16, with 3 consecutive full runs green. New in `e2e/playtest.spec.ts`:
  - play to an ending, Back, reload, and a forced roll
  - two batches, the dashboard, a replay, compare, and heat on the canvas
  - coverage finds an orphan node

## Performance
- **Bot batches:** 5,000 random-bot games take 5.9 s (basic) and 3.5 s (advanced) on 4 cores; on one core, 19 s and 12 s. Combat dice dominate.
- **Coverage walk:** the engine test book needs about 5.6k situations (about 10–20 s). It runs as a job, capped at 20k situations by default.

## Decisions
- ADR 0008: a stateless player, runs stored as pick indices with the bundle, aggregates computed once, and a process pool.
- Bots never sell, never unequip, and only equip into empty slots.
- "Lift" is a correlation (win rate held vs not held), and the UI says so.

## Known issues / notes
- Batches don't record an engine version; an engine change could reinterpret old pick lists (ADR 0008).
- The coverage walker ignores exact stat values (documented in the UI) and can be slow on fight-heavy books. The visit cap (4) can miss `visits(x) > 4` gates.
- Batch summaries are computed after all runs, so memory holds every run record (bounded by the 2M-step cap).
- `list_batches`/`get_batch` rebuild the current content hash on every call (fine at this scale).
- Item lift counts any item ever held, including ones taken away later.
- The player shows beat notes until Phase 7 adds prose.

## Phase 6 starting points
1. The state digest (must/may have) can reuse the walker's state signatures as a cross-check for the dataflow analysis.
2. New validation (never/always-satisfiable gates, softlocks, can't-reach-ending) can use the coverage walk's unreachable list as a slower ground truth.
3. The lore wiki gets the master–detail pattern from `features/entities/MasterDetail.tsx`.
