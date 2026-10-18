# v2 Phase 7 — LLM infrastructure & prose pipeline

**Status:** Complete · **Date:** 2026-10-18 · **Branch:** `v2`

## What was built

### LLM layer (`backend/src/gamebook/llm/`)
- **`client.py`:** an OpenAI-compatible client (httpx, synchronous for the job thread).
  - Retries connection errors, timeouts, 408/409/425/429 and 5xx with backoff, honouring Retry-After.
  - If `response_format` is rejected, it retries without it.
  - Token usage comes from the server, or is estimated at about 4 characters per token.
  - Per-provider concurrency semaphores; `list_models()`.
- **`fake.py`:** the offline test model. It is deterministic: the writer works from the beat notes and choices, and the critic scores 6, then 8 after an edit, so the loop is exercised. `SCRIPT` queues exact replies per role for tests.
- **`jsonparse.py`:** tolerant JSON extraction (code fences, chatter, trailing commas, braces inside strings).
- **`templates.py`:** default system/user prompts for writer, critic, editor and summarizer; a sandboxed Jinja2 renderer with strict undefined; the critic's JSON schema and six-score rubric.

### Data (migration 0006)
- `llm_provider`, `prompt_template` (versioned, one active per role), `llm_call` (the full log), `pipeline_run` (trail), `prose_version`, and `series.writing` (pipeline settings).

### Services & API
- **Providers:**
  - `GET/POST /llm/providers`, `PATCH/DELETE /llm/providers/{id}` (deletion is refused while a series uses the provider).
  - `POST /llm/providers/{id}/test` connects and lists the provider's models.
- **Templates:**
  - `GET /llm/templates`
  - `POST /llm/templates/{role}` saves a new version and makes it active.
  - `POST /llm/templates/{id}/activate`
  - `POST /llm/templates/{role}/preview` renders a template against a real section.
- **Call log and costs:** `GET /llm/calls` (filters), `GET /llm/calls/{id}`, `GET /llm/costs` (by role, model and day).
- **Writing settings:** `GET/PUT /series/{id}/writing-settings`.
- **Writing:**
  - `GET /books/{id}/writing-queue`: every variant in canonical order with its status (none/draft/in review/approved/stale).
  - `GET /nodes/{id}/prose`
  - `GET /variants/{id}/context`: the assembled context, token estimates and what was trimmed.
  - `POST /variants/{id}/prose` (write by hand), `POST /prose/{id}/approve` (optionally with edits), `POST /prose/{id}/reject`, `PUT /prose/{id}/summary`
  - `POST /variants/{id}/generate` and `POST /acts/{id}/generate` run as jobs; act generation filters missing/stale/all and takes a budget.
  - `GET /pipeline-runs/{id}`
- **Context assembler (`services/writing_context.py`):** `BookData` loads a book once; `assemble` builds the context (SPEC §5.1), trims it to the budget, and hashes the staleness inputs.
- **Problems:** `prose_stale` (info).
- **Player:** shows approved prose for the variant being read, falling back to beat notes.
- **Git export/import:** carries approved prose; undo snapshots don't (ADR 0009).

### Frontend
- **Settings** (`/settings`):
  - Providers: presets for a local server, OpenAI, OpenRouter and the offline model; base URL; key *variable* with a "set on the server" indicator; parallel calls; a models table with prices; test connection, and add models from the server's list.
  - Prompt templates: per role; edit, save as a new version, switch versions, and preview against any section of the last-opened book.
  - Call log & costs: totals by role, a filterable log, and full messages/response per call.
- **Writing** (`/writing/:bookId`):
  - Queue in canonical order, grouped by act, with status filters and counts.
  - Review:
    - **"What the writer sees"**: collapsible context with a token meter and trimmed sections.
    - **Draft**: version picker, editable prose, word diff against the previous version, Approve / Approve with my edits / Reject / Discard edits, and an editable summary.
    - **Critique trail**: rubric scores per pass, issues with quotes and suggestions, cost, the author's notes.
  - Generate and regenerate with notes.
  - **Pipeline settings** dialog: provider and model per role, temperature, max tokens, pass score, maximum rewrites, context budget.
  - **Write an act** dialog: which sections, a budget, live progress.
- **Story inspector:** the Beat tab shows prose status per variant, with links to the Writing review.
- **Player:** renders approved prose.

## Tests
- **Backend:** 424, plus 1 opt-in live test.
  - `test_llm_client.py`: retries, no retry on 4xx, giving up, the `response_format` fallback, a missing key variable, listing models, tolerant JSON.
  - `test_writing.py`:
    - providers, versioned templates and preview
    - context content and budget trimming
    - the writer → critic → editor loop with logging and costs, and the threshold short-circuit
    - a bad critic reply retried once, and failure after two bad replies
    - a missing model gives 422
    - approve/reject/edits and stale propagation through the predecessor, `prose_stale` problems
    - writing an act in canonical order with budget stops
  - The tree round trip now includes approved prose.
- **Frontend unit:** 57 (new: word diff).
- **Browser:** 21. New in `e2e/writing.spec.ts`: providers and template versions; generate → critique trail → approve with edits → diff → prose in the player → stale after a beat-note change → inspector status; write a whole act.

## Decisions
See ADR 0009: prose beside the graph (soft references, outside undo), keys in environment variables, the offline model as a provider kind, staleness as a hash of the assembled context.

## Known issues / notes
- Token counts are estimates when servers don't report usage.
- Generation jobs run one at a time (the single job worker). Provider concurrency limits matter once several jobs or assists run together.
- The writer context uses the digest at the highest tier: tier-specific "only some readers have" facts (such as class skills) appear for every tier.
- Provider `headers` are stored in plain text (secret-looking values are masked in the API): prefer `api_key_env`.
- Generation jobs share the single job worker with playtest batches, so a long "Write an act" delays other jobs.
- Rejecting a version uses a browser prompt for the reason; a proper dialog would be better.
- **Not deployed yet:** the user was benchmarking their LLM server, so the app on :8788 wasn't restarted. Run `make deploy` when convenient.

## Bug pass (independent review)
Thirteen findings, all fixed; regression tests in `test_writing.py`:
1. **Context trimming could loop forever** (pegging a CPU and hanging `/problems`, the queue and the job thread) when beat notes alone exceeded the budget. Trimming now always terminates, dropping the previous section's text if it still can't fit.
2. **Setting only temperature or max tokens for the critic broke every generation.** Roles without their own provider and model now use the writer's, keeping their own temperature and max tokens.
3. **The JSON retry's cost was dropped,** and the "your previous reply" nudge didn't include that reply. Costs now combine both calls, and the bad reply is sent back as the assistant turn.
4. **Approving a predecessor's draft unchanged marked approved successors stale.** The hash now uses the predecessor's text, not its approval status or the draft marker.
5. **"Re-approve if it still fits" had no button.** Stale approved text can now be re-approved.
6. **Old versions couldn't be restored.** Approving a superseded or rejected version (with or without edits) creates a new approved version whose parent is the old one.
7. **The act budget missed the cost of failed sections, and a provider disabled mid-batch aborted the whole batch.** `LlmError` now carries what was already spent, and service errors fail only that section.
8. **Duplicate generation jobs could queue for the same section.** Starting one while another is queued or running for it (or for any section of an act being written) returns 409.
9. **Secret-looking provider headers were returned by the API.** Values of headers named like auth, key, token, secret, cookie or password are masked; sending the mask back keeps the stored value. `api_key_env` must be named `…_KEY` or `…_TOKEN`.
10. **Story edits left prose status and the queue stale in the UI.** Writing queries now live under `['book', id]`, and "write an act" completion refreshes the book.
11. **`/problems` built the snapshot twice,** and finding a variant's node scanned the whole book. The snapshot is now shared, and variants are looked up through a map.
12. **The structured-output fallback depended on the error's wording.** Any 400/422 on a schema request now retries without the schema.
13. **Deleting or replacing a series wiped its call log and cost history.** `llm_call.series_id` is now `SET NULL`.

Polish from the same review:
- **Client:** HTTP clients are closed after each call; timeouts aren't retried, so a slow model isn't re-billed.
- **Critic replies:** `issues: null` is tolerated.
- **Summaries and context:** approving an unedited version keeps its pipeline summary; characters and beats are in a stable order in the context and hash; "previous section" is listed as trimmed only when it existed.
- **Timestamps:** naive datetimes are serialised as UTC in every response.
- **Queue:** grouped by act id, since titles can repeat.
- **Template editor:** switching roles asks before discarding unsaved edits.

## Phase 8 starting points
1. **Consistency checker:** reuse `BookData` + `assemble` for context, and add a `consistency` role and template; issues go to Problems with quotes.
2. **Beat/branch suggester and lore extractor:** new roles with JSON schemas through `call_json`; drafts as reviewable entities.
