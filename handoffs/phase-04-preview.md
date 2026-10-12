# Phase 4 Handoff — Preview Mode (Reader Experience)

## Phase 4: Preview Mode (Reader Experience)

### Completed
1. **Preview Mode Navigation**: Nodes can be accessed and navigated through in preview mode. Entry nodes start the preview, beat nodes show content with choices.
2. **Inventory Tracking**: Items can be added to nodes and tracked as the reader progresses. Item effects are stored as JSON and properly serialized to/from SQLite.
3. **Story Text Rendering**: Nodes support `storyText` (AI-generated prose) and `description` (fallback). Preview mode shows `storyText` when available, otherwise `description`.
4. **Multiple Endings Tracking**: Ending-type nodes are properly created and identified.
5. **End-of-Game Summary**: The framework supports tracking which ending was reached.
6. **Combat/Encounter System (Basic)**: Encounters can be created with stats (JSON-serialized), associated with nodes, and tracked during preview.

### Bugs Fixed
1. **Item `effect` serialization**: The `effect` column stores JSON strings but routes were passing raw Python dicts to SQLAlchemy, causing SQLite binding errors. Fixed by adding `json.dumps()` on write and `json.loads()` on read in `items.py`.
2. **Node `items`/`encounters`/`choices` serialization**: The `create_node` route was passing raw Python lists to SQLAlchemy columns that are `String` type. Fixed by serializing with `json.dumps()` on write. All list/get endpoints now parse JSON strings back to lists on read.
3. **Node `storyText` not persisting**: The `create_node` route wasn't passing `storyText`, `storyStatus`, `storyModel`, or `storyPrompt` from the request body to the Node constructor. Fixed by adding these fields.
4. **Encounter `stats` missing from response**: The `create_book_encounter` response was missing the `stats` and `recurring` fields. Fixed by adding them with proper JSON parsing.

### Files Changed
- `app/routes/items.py`: Added `json`/`uuid` imports; fixed `effect` serialization in `create_shared_item`, `create_book_item`, and `update_item`.
- `app/routes/nodes.py`: Fixed `create_node` to serialize `items`/`encounters`; added `storyText`/`storyStatus`/`storyModel`/`storyPrompt` to Node constructor and response; all list/get endpoints now parse JSON fields.
- `app/routes/encounters.py`: Added `stats`/`recurring` to `create_book_encounter` response.

### Test Suite Added
- `tests/test_phase4.py` — 12 tests across 6 classes:
  - `TestPreviewModeNavigation` (4 tests): Entry node start, node content, choices, ending nodes
  - `TestInventoryTracking` (2 tests): Items persist, items tracked
  - `TestStoryTextRendering` (2 tests): storyText priority, description fallback
  - `TestMultipleEndings` (1 test): Multiple ending nodes
  - `TestEndOfGameSummary` (1 test): Ending node creation
  - `TestCombatEncounterSystem` (2 tests): Encounter with stats, encounter on node

### Test Results
- **58/58 tests pass** (46 existing + 12 new Phase 4 tests)

## Phase 5: Ongoing Quality Bar

Phase 5 is NOT a one-off phase — it's an ongoing quality bar applied to ALL subsequent phases. Every phase must include these quality attributes:

### Phase 5 Quality Attributes (Ongoing)
1. **Auto-save**: Debounced save to localStorage (30s interval) with restore on reload
2. **Undo/Redo**: 20-step undo/redo stack for canvas operations
3. **Export Formats**: JSON export (done) + PDF export (pending)
4. **Accessibility**: ARIA labels, keyboard navigation, focus management
5. **Responsive Layout**: Works on tablets and mobile
6. **Error Handling**: User-friendly error messages, retry logic
7. **Confirmation Dialogs**: Before destructive actions (delete, discard)

### Phase 5 Status in This Phase
These Phase 5 attributes were tested/verified during Phase 4:
- ✅ JSON export format (tested via `test_export_series_returns_valid_json`)
- ✅ Data integrity with JSON serialization
- ⬜ Auto-save — not yet implemented
- ⬜ Undo/Redo — not yet implemented
- ⬜ PDF export — not yet implemented
- ⬜ Accessibility (ARIA/keyboard) — not yet implemented
- ⬜ Responsive layout — not yet implemented
- ⬜ Error handling — partial (404s work, but user-facing errors need improvement)
- ⬜ Confirmation dialogs — not yet implemented

## Phase 6 Handoff — What Comes Next

### Phase 6: AI Story Generation Engine

Based on the spec, Phase 6 involves building the AI story generation engine that:

1. **Integrates with OpenRouter API** (or similar) for text generation
2. **Generates storyText** for beat nodes based on:
   - Node title and description
   - Previous node context (story continuity)
   - Reader's inventory and stats
   - Act/scene context
3. **Manages storyStatus** transitions: pending → generating → complete/error
4. **Supports storyModel selection**: Different models for different tones/lengths
5. **Builds storyPrompts**: Templates that include context from the player's journey so far

### Key Implementation Details
- The Node model already has `storyText`, `storyStatus`, `storyModel`, `storyPrompt` fields
- The `create_node` route now properly accepts these fields
- The `update_node` route already supports updating them
- Need to add a new endpoint: `POST /api/books/{book_id}/nodes/{node_id}/generate-story`
- Need to add frontend UI for triggering and viewing AI-generated story text

### Phase 5 Quality to Apply
- Auto-save should be implemented in Phase 6 (debounced save of generated stories)
- Undo/redo for story generation (regenerate with different prompts)
- Error handling for API failures with retry logic
- Accessibility for the story generation panel

### Testing Requirements for Phase 6
- Unit tests for story generation logic (prompt building, response parsing)
- Integration tests for the `generate-story` endpoint
- Tests for error handling (API failures, rate limits, invalid responses)
- Tests for the `storyStatus` state machine
- E2E tests for the story generation workflow

### Dependencies
- `openai` package (or `httpx` for raw API calls)
- Environment variable for API key: `OPENROUTER_API_KEY`
- The existing Node model fields (`storyText`, `storyStatus`, `storyModel`, `storyPrompt`)
- The existing Choice model for story continuity (previous node → current node)

## Handoff Notes
- All tests pass (58/58)
- No breaking changes to existing API
- The JSON serialization pattern (json.dumps on write, json.loads on read) should be followed consistently across all routes
- The `items.py` and `encounters.py` routes use a shared-specific pattern (series_id vs book_id) that should be followed for future entity types
- Phase 5 quality attributes are ongoing — they must be tested in every phase, not just implemented once
