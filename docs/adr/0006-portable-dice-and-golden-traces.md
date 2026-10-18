# ADR 0006 — Portable dice (PCG32) and golden traces

**Status:** Accepted (2026-10-18)

## Context
Every playthrough must be replayable from (book, tier, seed, actions), and the
standalone player (Phase 12) will re-implement the engine in TypeScript. If both
runtimes don't roll *identical* dice, traces can't prove parity. Python's
`random.Random` (MT19937 + `_randbelow`) is impractical to reproduce exactly in TS.

## Decision
- `gbx.SeededRng` is **PCG32 (XSH-RR)** with a fixed increment, seeded like
  `pcg32_srandom`, and bounded rolls by **rejection sampling** (no modulo bias).
  Reference vectors are pinned in `tests/core/test_gbx.py`.
- A **golden trace** (`gamebook-trace` v1) is JSON: the game bundle, tier, seed,
  character-creation options, the action list, and the expected events and final
  state. `engine.trace.record/replay`; traces live in `backend/tests/core/golden/`
  and are regenerated only deliberately (`GOLDEN_UPDATE=1`).
- The **game bundle** (`gamebook-bundle` v1, `engine.bundle`) is the JSON form of a
  `BookSnapshot`; it round-trips exactly.

## Consequences
The TS runtime must implement PCG32, gbx and the engine to replay every golden trace
identically — a precise, testable target. Any intentional behaviour change shows up
as a golden-trace diff that has to be accepted explicitly.
