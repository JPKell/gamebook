# ADR 0010: LLM players in playtest batches

**Status:** Accepted (2026-10-18)

## Context
Phase 9 lets a model play the book as a reader. Unlike bots, each step is a paid,
slow and non-deterministic model call. A batch can be interrupted (cancel, a spending
cap, a crash). We needed to decide how LLM runs are stored, replayed, bounded and
continued, without forking the bot pipeline of ADR 0008.

## Decision
- **The same run format as bots.** An LLM run is stored as pick indices into
  `Game.available()`, so it replays exactly on the batch's bundle with the same code
  (ADR 0008). The engine still rolls every die: the model only chooses.
  - Per step, the run also stores the player's **notes**: chosen option, reasoning,
    and whether (and why) it was confused. `notes[i]` is the decision made at step `i`.
    Replays return it as `next_note`.
- **One chooser interface.** `core.sim.play_with(book, tier, seed, choose)` plays a game
  with any chooser. Bots and LLMs are two choosers. A chooser raises `StopRun` to end
  a run early, and the run is recorded as `stopped`.
- **The model sees only the reader's page.** `core.sim.reader.render_page` renders the
  page text: approved prose (else the beat notes), what just happened, the adventure
  sheet, and any fight. It lists the options separately. Section titles, keys,
  conditions and hidden state are never shown. Memory is the model's own rolling
  summary, capped at 600 characters.
- **Runs are saved as they finish**, along with their cost. The batch's cost is a running
  total, added to atomically on every call, so it survives replays and crashes. Games run
  in parallel, up to `min(4, provider.max_concurrency)`, in threads inside the batch's
  job. The job runs on the runner's separate `llm` lane.
- **Model failures end a run as `llm_error`**, not a content `error`. Three in a row halt
  the batch as `failed`.
- **Budgets are checked before each call** (re-asks included). Once the batch's spend
  reaches the cap, games stop and the batch ends `stopped`. Overspend is bounded by the
  calls already in flight: one per parallel game.
- **Resume, don't restart.** `POST /batches/{id}/resume {budget_usd?}` starts a new job
  that plays only the missing runs. `stopped` and `llm_error` runs are deleted and
  replayed fresh; their spend stays in the batch total. A cancelled, failed (including a
  process restart) or stopped batch can be resumed.
- **The summary is rebuilt by replaying stored picks.** It covers every run across
  resumes, not just the latest job's. LLM batches add `summary.llm`: steps, confused
  steps, cost, stopped runs, and confusion grouped by node with sample notes.

## Consequences
- The dashboard, run viewer, heat map and comparison all work for LLM batches
  unchanged. LLM vs. bot and model vs. model are ordinary batch comparisons.
- Rebuilding the summary costs one replay per run. That is cheap at the LLM caps of 200
  runs × 400 steps.
- LLM batches don't block other jobs, but two LLM batches run one after the other.
- Reruns are not reproducible: a resumed or re-played run can differ. Stored runs always
  replay exactly.
