# Gamebook Authoring Tool — Handoff Index

## Workflow

Each phase follows this cycle:
1. Review previous handoff
2. Write code for current phase
3. Thorough bug review
4. **Write extensive test suite for that phase**
5. Write handoff for next phase
6. Clear context, repeat

Phase 5 (Polish & Export) is an **ongoing quality bar**, not a one-off phase. Every phase should add to it:
- Auto-save (debounced saves + visual indicator)
- Undo/Redo (20-step stack)
- Export formats (JSON works, PDF next)
- Accessibility (ARIA labels, keyboard nav)
- Responsive layout
- Error handling
- Confirmation dialogs

| Phase | Topic | File | Status |
|-------|-------|------|--------|
| 1 | Project Scaffold & Data Model | `handoffs/phase-01-scaffold.md` | ✅ Complete |
| 2 | Graph Canvas — Core UX | `handoffs/phase-02-canvas.md` | ✅ Complete |
| 3 | Bug Pass & Stability Fixes | `handoffs/phase-03-bugfix.md` | ✅ Complete |
|| 4 | Preview Mode (Reader Experience) | `handoffs/phase-04-preview.md` | ✅ Complete |
|| 5 | Comprehensive Test Suite & Bug Fixes | `handoffs/phase-05-testing.md` | ✅ Complete |
|| 6 | Inference Integration (Bridge) | `handoffs/phase-06-inference.md` | ✅ Complete |
|| 7+ | See `plan.md` | | |
