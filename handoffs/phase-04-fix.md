# Phase 4 — Preview Mode (Reader Experience)

**Date:** 2026-10-12  
**Status:** In Progress  
**Previous Phase:** Phase 3 (Bug Pass & Stability Fixes) — `handoffs/phase-03-bugfix.md`

---

## What was done

### Preview Mode (Partial Implementation)

The preview mode is implemented in `app/static/js/app.js` as `startPreview()`. It:

- Finds entry nodes (or uses the first node if no entry nodes exist)
- Renders node content (title, description, items, encounters, choices)
- Supports forward navigation through choices
- Includes a "Back" button for history navigation
- Shows "The End" at ending nodes
- Works entirely in the browser — no API calls

### What's Missing (Phase 4 Completion)

1. **Story text rendering** — If nodes have `storyText` populated (from AI generation), the preview should show that instead of the node's description.

2. **Inventory tracking** — Items picked up on one node should persist through the preview session. Currently, items are shown but not tracked.

3. **Multiple endings tracking** — Track which ending nodes were reached and how many times.

4. **End-of-game summary** — Show a recap of all paths taken and endings reached.

5. **Preview from entry point** — Allow starting preview from any node, not just the first entry node.

6. **Combat/Encounter System** — Not implemented yet. This is a significant feature that needs its own design.

---

## Files modified

| File | Change |
|------|--------|
| `app/static/js/app.js` | Added `startPreview()` function and `runValidation()` function |
| `app/static/index.html` | Added Preview button to toolbar |

---

## Test status

- 46 tests passing (from Phase 5 comprehensive suite)
- **No Phase 4-specific tests yet** — this needs to be added

---

## What's next — Phase 5

Phase 5 (Polish & Export) includes:

1. **Auto-Save** — Debounced save to database every 30 seconds + on every change
2. **Undo/Redo** — Already implemented (Ctrl+Z working, 20-step stack)
3. **Export Formats** — JSON export works, PDF export needs work
4. **Accessibility & Polish** — Keyboard navigation, ARIA labels, responsive layout, error handling, confirmation dialogs

**Note:** Phase 5 is an ongoing quality bar. Every phase should add to it.

---

## Next Steps

1. Complete Phase 4 (Preview Mode) with missing features
2. Write comprehensive test suite for Phase 4
3. Begin Phase 5 (Polish & Export) as an ongoing quality bar
