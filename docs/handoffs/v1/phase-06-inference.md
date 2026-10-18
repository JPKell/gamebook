# Phase 6 — Inference Integration (Bridge)

**Status:** Complete
**Date:** 2026-10-12
**Quality Bar:** Phase 5 (error handling, validation)

## What Was Done

Phase 6 bridges the app to the external AI inference endpoint (configured via `INFERENCE_ENDPOINT` and `INFERENCE_API_KEY`).

### 1. Enhanced `app/services/inference.py` (rewritten)

The previous `send_completion` was a bare-bones async function with no retries, no logging, and hardcoded timeout/config.

**Rewrote with:**
- **Exponential backoff retries** — reads `settings.inference.max_retries` from config (default 3). Retries on `ConnectError`, `TimeoutException`, and 5xx `HTTPStatusError`. Non-retryable 4xx errors propagate immediately.
- **Structured logging** — logs every attempt, response size, and failures.
- **`check_health()` function** — lightweight probe that returns `{status, endpoint, message}`. Used by the health check endpoint. Handles three states: `healthy`, `unhealthy`, `not_configured`.

### 2. New `app/routes/inference.py`

Two new API endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/inference/status` | Health check for inference endpoint |
| `POST` | `/api/books/{book_id}/nodes/{node_id}/generate` | Generate story text for a node |

**`POST /generate` flow:**
1. Validates book and node existence (404 on missing)
2. Sets `storyStatus = "generating"` on the node
3. Builds a prompt from: node title/description/type, location, items (resolved with names/descriptions), encounters, previous node's `storyText` (for continuity), act context
4. Calls `inference.send_completion()` with optional `model`, `temperature`, `max_tokens` parameters
5. On success: saves `storyText`, sets `storyStatus = "complete"`, records `storyModel` and `storyPrompt`
6. On failure: sets `storyStatus = "failed"`, records `storyPrompt`, returns 502

### 3. Prompt Building (`_build_story_prompt`)

The prompt construction includes:
- System context (genre/style instructions)
- Node metadata (title, type, description)
- Resolved items (name + description from DB)
- Resolved encounters (name + description from DB)
- Previous node's `storyText` for continuity (found by tracing `Choice` → `target_id == node.id`)
- Act title
- Generation instruction (100–500 words, vivid, engaging)

### 4. App Registration

- Added `inference` router to `app/__init__.py` with `prefix="/api"` and `tags=["inference"]`

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `app/services/inference.py` | **Rewritten** | Retry/backoff, logging, `check_health()` |
| `app/routes/inference.py` | **Created** | Two new API endpoints + prompt builder |
| `app/__init__.py` | **Modified** | Registered `inference` router |

## Files Created

| File | Lines | Description |
|------|-------|-------------|
| `app/routes/inference.py` | ~220 | Inference routes (health check, story generation) |
| `tests/test_phase6.py` | ~410 | 14 tests across 5 test classes |

## API Endpoints

### `GET /api/inference/status`
Returns inference endpoint health status.

**Response:**
```json
{
  "status": "not_configured",
  "endpoint": "http://localhost:8442/v1/chat/completions",
  "message": "Inference endpoint not configured..."
}
```

Status values: `"healthy"`, `"unhealthy"`, `"not_configured"`

### `POST /api/books/{book_id}/nodes/{node_id}/generate`
Generates story text for a node.

**Request body (optional):**
```json
{
  "model": "gpt-3.5-turbo",
  "temperature": 0.7,
  "max_tokens": 2000
}
```

**Response (success 200):**
```json
{
  "id": "node-uuid",
  "title": "Dark Corridor",
  "storyText": "You walk down the dark corridor...",
  "storyStatus": "complete",
  "storyModel": "gpt-3.5-turbo",
  "storyPrompt": "You are writing a story beat..."
}
```

**Response (failure 502):**
```json
{
  "detail": "Story generation failed: <error message>"
}
```

## Bugs Found & Fixed

| # | Bug | Fix |
|---|-----|-----|
| 1 | `send_completion` had no retry logic | Added exponential backoff (2^n seconds) with configurable max_retries |
| 2 | `send_completion` had no logging | Added structured logging for all attempts and responses |
| 3 | `check_health` function didn't exist | Created with three-state status reporting |
| 4 | No `storyStatus` tracking on generation | Node status transitions: pending → generating → complete/failed |
| 5 | Prompt had no context (items, encounters, previous text) | Built `_build_story_prompt` that resolves items, encounters, and previous story text from DB |
| 6 | Pydantic deprecation warning on `model_fields` access | Changed from instance access to class access (`__class__.model_fields`) |

## Test Suite

**14 tests in 5 classes:**

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestInferenceHealthCheck` | 2 | Health endpoint returns status, reports not_configured |
| `TestStoryGeneration` | 5 | Success, status transitions, 404s, model tracking |
| `TestInferenceRetry` | 1 | Retry logic exists in code |
| `TestPromptBuilding` | 4 | Node title, items, encounters, previous story text |
| `TestStoryStatusTransitions` | 2 | Complete path, failed path |

## Phase 5 Quality Bar Applied

- **Error handling:** `HTTPException` on missing book/node, 502 on inference failure, status tracked
- **Validation:** Book/node ownership verified before generation
- **Logging:** All inference calls logged

## Known Issues

- No frontend UI yet for "Generate Story" button (Phase 7+)
- Prompt is basic — no series tone/genre awareness
- No streaming support (wait-for-full-response pattern)
- `check_health` uses a simple GET; some endpoints may not support GET

## Next Steps (Phase 7 — Story Generation)

Phase 7 builds on this bridge:
- Multi-node generation (generate entire act or book)
- Series tone/genre context in prompts
- Streaming responses (SSE) for long generations
- Generation progress tracking
