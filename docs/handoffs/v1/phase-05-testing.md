# Phase 5 — Comprehensive Test Suite & Bug Fixes

## What was done

### New test suite: `tests/test_comprehensive.py` (38 tests)

Covers scenarios the original 8 tests missed, including the two bugs that broke in production:

| Test | What it verifies |
|------|-----------------|
| `test_get_series_by_id_includes_books` | GET /series/{id} returns books (regression: was 500) |
| `test_get_series_by_id_returns_entities` | Series GET returns locations, items, encounters |
| `test_get_book_standalone_not_confused_by_series_prefix` | /api/books/{id} not captured by /series/{id}/books |
| `test_full_roundtrip` | Full hierarchy: series→book→acts→nodes→choices |
| `test_node_types_preserved` | entry/beat/ending types stored correctly |
| `test_node_position_stored` | x/y coordinates persisted |
| `test_act_ordering_auto_assigned` | Acts auto-number 1, 2, 3... |
| `test_shared_location_belongs_to_series` | Locations scoped by series vs book |
| `test_book_location_is_not_shared` | Book-specific locations separate from shared |
| `test_shared_and_book_entities_are_separate` | Same name, different scopes |
| `test_item_with_effect` | Item effect field stored |
| `test_encounter_with_stats` | Encounter stats as JSON, recurring flag |
| `test_update_act_fields` | Act title, hasEndings, entry/exit nodes |
| `test_delete_act_removes_it` | Act deletion, nodes survive |
| `test_act_not_found_when_wrong_book` | Cross-book access denied |
| `test_create_node_without_act` | Orphan nodes allowed |
| `test_create_node_with_invalid_act_returns_404` | Invalid act_id rejected |
| `test_delete_node_removes_from_act` | Node removal from act nodeIds |
| `test_delete_node_cascades_to_choices` | Choices deleted with source node |
| `test_create_choice_to_self_fails` | Self-loop rejected (400) |
| `test_delete_choice_removes_from_node` | Choice removal from source node |
| `test_choice_text_stored_correctly` | Choice text preserved |
| `test_create_series_without_title_fails` | Missing title rejected |
| `test_get_nonexistent_series_returns_404` | Invalid series ID |
| `test_update_series_fields` | Series title, tone, worldGuidelines |
| `test_list_series_sorted_by_created_desc` | Series sorted newest first |
| `test_export_series_returns_valid_json` | Export structure with version, series, books |
| `test_export_series_with_shared_entities` | Export includes shared locations/items/encounters |
| `test_cascade_delete_series_removes_all_books` | Full cascade on series delete |
| `test_cascade_delete_series_removes_shared_entities` | Shared entities deleted with series |
| `test_get_empty_series` | Empty series returns valid data |
| `test_book_with_no_acts` | Empty book returns valid data |
| `test_list_books_for_nonexistent_series` | Empty list for missing series |
| `test_update_node_description_and_type` | Node description/type update |
| `test_update_node_assigns_act` | Reassigning node to different act |
| `test_act_entry_exit_node_ids_persist` | Act entry/exit node IDs stored as JSON |
 
### Bugs found and fixed

1. **`app/routes/acts.py:64`** — Act order auto-assignment crashed on first act.
   `session.query(Act.order)....first()` returns `None` when no acts exist. `None[0]` → `TypeError`.
   **Fix:** `order = ((max_order[0] or 0) + 1) if max_order else 1`

2. **`app/routes/locations.py`** — Create endpoint response missing `description` field.
   **Fix:** Return `{"id", "name", "description", "shared": ...}` instead of just `{"id", "name", "shared"}`

3. **`app/routes/items.py`** — Create endpoint response missing `description` and `effect` fields.
   **Fix:** Return full fields in response

4. **`app/routes/encounters.py:71`** — `stats` (Python dict) not JSON-serialized before DB insert.
   SQLite driver doesn't accept `dict` as parameter binding value.
   **Fix:** `json.dumps(stats) if stats else None`

5. **`app/routes/encounters.py:74`** — Create response missing `stats`, `recurring`, `seriesId` fields.
   **Fix:** Return all relevant fields, deserialize `stats` from JSON on read.

6. **`app/routes/encounters.py`** — `uuid` import was inside a function but used at module level in another function.
   **Fix:** Moved `import json` and `import uuid` to top of file.

## Files modified

- `tests/test_comprehensive.py` — **new**, 38 tests
- `app/routes/acts.py` — Act order calculation fix
- `app/routes/locations.py` — Create response includes description
- `app/routes/items.py` — Create response includes description and effect
- `app/routes/encounters.py` — JSON serialization of stats, complete responses, imports
- `app/models/encounter.py` — Added `__repr__`

## Test results

- 38/38 comprehensive tests passing
- 8/8 original tests passing (no regression)

## Next steps

Phase 6 (Preview Mode) is next per the plan.
