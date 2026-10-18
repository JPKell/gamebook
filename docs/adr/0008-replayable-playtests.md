# ADR 0008: Replayable playtests (stateless player, pick-index runs)

**Status:** Accepted (2026-10-18)

## Context
Phase 5 adds an in-app player, bot batches of thousands of games, and a run viewer. We
needed to decide what to store and where game state lives.

## Decision
- **The player is stateless on the server.** The client keeps
  `{tier, seed, class, inputs[]}` (in localStorage) and posts it to
  `POST /books/{id}/play`. The server replays everything and returns the view.
  - *Back* drops the last input; *restart* clears them.
  - Debug moves (jump, set state, force a roll) are inputs too, so a debugged
    playthrough is still reproducible.
  - If the book changed so an input no longer applies, replay stops there and says so.
- **Bot runs are stored as pick indices into `Game.available()`**, plus the batch's game
  bundle and its SHA-256 content hash. A run replays exactly on the bundle it was
  played on, even after the book is edited. A batch whose hash differs from the current
  book is flagged "stale".
  - Bots draw from their own `random.Random(f"{bot}:{seed}")`, never the game's dice.
- **Batches run as background jobs.** A persisted `Job` row is worked by one thread,
  which fans out to a `spawn` process pool (one worker per core by default,
  `sim_processes`). Progress streams over SSE. On restart, jobs and batches left
  running are marked failed.
- **Per-batch aggregates are computed once, at the end** (`core.sim.summarize`) and
  stored as JSON. Per-step rows are not stored; replay reconstructs them.

## Consequences
- **Storage is small:** about 1 MB for a 5,000-run batch plus the bundle, and
  dashboards are a single read.
- **Replays reuse the engine:** the run viewer and the player are the same code path.
- **Determinism is load-bearing:** engine changes that alter `available()` order, or
  dice use, change what an old pick list means. The stored bundle pins the content but
  not the engine version, so a future engine bump should store an engine version on
  batches.
- **Replay cost:** each player request is O(moves), which is fine for a single author.
  Inputs are capped at 5,000.
