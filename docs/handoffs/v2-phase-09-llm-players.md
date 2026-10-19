# v2 Phase 9 — LLM players

**Status:** Complete · **Date:** 2026-10-18 · **Branch:** `v2`

Built and tested against the offline model only. No real LLM endpoint was contacted; a live smoke test needs the user's URL, model and key env var, and their go-ahead.

## What was built

### Backend
- **`core/sim/batch.py`:**
  - `play_with(book, tier, seed, choose)` plays a game with any chooser; `play_run` (bots) is now a thin wrapper around it.
  - A chooser raises `StopRun` to end a run early. The run is recorded as `stopped`.
- **`core/sim/reader.py`:** `render_page`, the reader's page as plain text.
  - The text is approved prose, else beat notes, else a "no text yet" marker.
  - Then what just happened, the adventure sheet and any fight. Options are listed separately.
  - It never shows titles, keys, conditions or hidden state.
- **Templates:**
  - A `player` role (`PLAYER_SCHEMA`: choice, reasoning, memory, confused, confusion).
  - Four `PERSONAS`: cautious, reckless, completionist, role-player.
  - The offline model attacks when it can, else takes option 1. It is confused by sections with no text.
- **Migration 0008:** `playtest_batch.cost_usd`; `playtest_run.notes` (JSON) and `playtest_run.cost_usd`.
- **Schemas:**
  - `BatchIn.player` is a bot or an `LlmPlayer`. A player without `kind` is a bot, so old clients still work.
  - `budget_usd` is optional. LLM caps are 200 runs and 400 steps.
  - `ResumeIn`; `RunOut.cost_usd` and `confused_steps`; `PlayOut.next_note`.
- **`services/llm_play.py`:**
  - The per-step chooser renders the page, keeps a rolling memory (≤ 600 chars) and validates the choice, re-asking once. It records a note per step and adds every cost (failed calls and retries included) to the run and the shared `Budget`.
  - `batch_job` seeds the templates once, then plays games in parallel (≤ 4, and no more than the provider's concurrency).
  - Each run is inserted as it finishes and the batch cost re-summed.
  - The summary is rebuilt by replaying every stored run (`rebuild_summary`) and adds `summary.llm` with confusion grouped by node.
- **`services/playtest.py`:** LLM batches are validated (the provider must exist and be enabled) and dispatched to `llm_play`.
  - `resume_batch` is only for LLM batches that aren't running or done. It needs the budget to have room, and keeps the old budget unless a new one is given.
  - Run lists include `confused_steps`; replays return `next_note`.
- **API:** `POST /batches/{id}/resume {budget_usd?}`.

### Frontend
- **New batch:**
  - A Bots / LLM players toggle.
  - LLM players get provider, model, persona and budget fields. Switching to LLM drops runs to 10 and steps to 200, and the inputs are capped at the backend limits.
  - Create errors are shown.
- **Batch list:**
  - The cost of LLM batches.
  - "stopped: budget reached".
  - A **Resume** button for stopped, cancelled or failed LLM batches; when the budget was reached, it asks for a new one.
- **Dashboard:**
  - A "Where players got confused" card: confused steps, cost and stopped runs, then nodes with sample notes. Each note opens that run's replay.
  - Confused and cost columns in the runs table.
- **Comparison:** confused-step rate and cost rows when both batches are LLM batches (model vs. model). LLM vs. bot uses the ordinary rows.
- **Replay:** a "Player's reasoning" panel shows the option chosen, the reasoning and any confusion.
- **Settings:** the `player` template is editable in Prompt templates. It isn't in Pipeline settings, because its model is chosen per batch.

## Bug pass (independent review)
The first review attempt hit a rate limit; the second confirmed 7 findings plus nits. All are fixed and covered by regression tests.

1. **A choice re-ask whose reply wasn't JSON crashed the run.** The `TypeError` had duplicate `previous`/`nudge` kwargs, and the paid call went uncounted. `call_json` now overrides the caller's re-ask arguments.
2. **Resume lost the spend of the runs it replayed**, so repeated stop/resume cycles could exceed the budget. The batch's `cost_usd` is now a running total, added to atomically on every call. It survives replays, crashes and restarts.
3. **A failing model or provider produced a "done" batch of error runs that couldn't be resumed.** Model failures now end the run as `llm_error`, not a content `error`.
   - Three failures in a row (any game) halt the batch as `failed`, with the reason.
   - Resume replays `llm_error` runs, as well as `stopped` ones.
4. **LLM batches blocked every other job.** The job runner now has a separate `llm` lane (its own worker), so writing, assists, coverage and bot batches keep running.
5. **Content-error events leaked conditions and expression names into the player's prompt.** `render_page` now drops `error` events.
6. **A crash in one game left the batch without a summary while the other games kept paying.** The first failure now halts the other games, and the summary is rebuilt in a `finally`. It also copes with a batch deleted while running.
7. **Deleting a resumed batch left its earlier jobs behind.** It now deletes every job whose payload names the batch.

Nits also fixed:
- **Budget checks:** the budget and stop switch are checked before every call, including re-asks.
- **Prompt size and markers:** the page is capped at 12k characters and options at 200. Book text can't close the prompt's `<page>`/`<options>` markers.
- **Model validation:** the model must be one the provider lists.
- **`_pick`:** a choice of `2.0` is accepted.
- **Resume form:** an inline new-budget form replaces `window.prompt`. It appears whenever the batch is over its budget, and accepts only an amount above what was spent.
- **Partial batches:** stopped, cancelled or failed batches that have a summary can be selected and compared.
- **Confusion links** open the replay at the confused step.
- **Providers with no models:** the form explains why Run is disabled.

## Tests
- **Backend:** 446, plus 1 opt-in live test. New in `tests/api/test_llm_play.py`:
  - Players play, cost money and explain themselves, with confusion grouped by node and `next_note` in replays.
  - The prompt holds only reader-visible text.
  - Prose reaches the page; a bad choice is re-asked.
  - A budget stops the batch and resume finishes it (422 while still over budget, 409 once done).
  - Validation: caps, unknown provider, unlisted model, persona; bots still work without `kind` and can't be resumed.
  - Regressions from the review:
    - a nested JSON re-ask
    - spend kept across resume
    - a failing model halts the batch, and resume replays it
    - deleting a resumed batch removes all its jobs
    - the LLM job lane doesn't block the main lane
    - content errors stay off the reader's page (`tests/core/test_sim.py`)
- **Frontend unit:** 57.
- **Browser:** 25. New: an LLM batch from the form, the confusion card, a replay with the player's reasoning.

## Known issues / notes
- LLM batches share one `llm` job lane, so two LLM batches run one after the other.
- Resumed or re-played LLM runs aren't reproducible (the model isn't); stored runs replay exactly.
- Budget overspend is bounded by calls already in flight: at most one per parallel game, since each call checks the budget first.
- Prose is read when the job starts, not from the batch bundle, so replays show today's approved prose.

## Phase 10 starting points
1. **Art library:** a new `asset` table with a content-addressed file store under `data_dir/assets`. Uploads go through the API with type and size checks; thumbnails are generated server-side.
2. **Node art placements** carry print controls (§2.13) and digital settings. The canvas card shows a thumbnail.
3. **Act and book art, maps and appendices** follow (PLAN Phase 10). The appendix builder's preview can reuse the print templates once Phase 11 lands, so a simple HTML preview is enough at first.
