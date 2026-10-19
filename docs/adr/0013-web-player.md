# ADR 0013: The standalone web player and engine parity

**Status:** Accepted (2026-10-19)

## Context
Phase 12 ships books to readers without the authoring server. The engine must therefore
run in the browser, and must behave exactly like the Python engine. Playtests, the print
verifier and every author's testing all rely on the Python engine's behaviour.

## Decision
- **A TypeScript port, proven by traces.** `frontend/src/engine` ports the gbx language
  (lexer, Pratt parser, evaluator), PCG32 dice, tier merging, the game engine, combat
  and narration, line for line from `core/`.
  - Numbers are exact BigInt rationals with Python's floor-based `%` and `floor`.
  - Python's `True == 1` equality and the compiled path's error messages are kept.
  - Both lexers accept ASCII only, and both engines reject integer results beyond 2^53
    ("number too large"), so the browser's doubles never round silently.
  - Python is the reference. Parity is checked in CI by the golden traces (full event
    diffs) and a generated corpus of 48 bot games over every tier, including a book
    with content errors. The corpus is compared by final state and a SHA-256 of the
    canonical event JSON, and a Python test fails if the corpus goes stale.
- **A static player with the book embedded.** The player is a separate Vite build:
  - One classic script with relative paths, so it runs from `file://` (module scripts
    are blocked there).
  - The book arrives as `book.js` setting `window.GAMEBOOK` rather than as fetched JSON,
    which `file://` would also block.
  - Over HTTPS a service worker caches every file, so the player installs and plays
    offline.
- **Saves are inputs.** A save is `{tier, seed, class, moves}`. Restoring a game, going
  back a step and autosaving all replay the moves, the same way the authoring app's
  stateless player works (ADR 0008). Saves stay in the reader's `localStorage`.
- **Everything is pre-rendered.** The codex pages come pre-rendered for every tier by
  the same templates as print. Bestiary and item entries carry their keys; the player
  injects CSS into a sandboxed frame to reveal only what the reader has met, so no
  author HTML runs as script.

## Consequences
- **Engine changes cost twice.** Every engine change must be made in both languages.
  The corpus test points at the regeneration command, and the TS parity tests show
  where the engines differ.
- **Saves are tied to the book.** Replaying moves against a re-exported, edited book can
  stop early. The player keeps the moves that still apply and stops there, rather than
  failing.
- **Size:** about 85 KB gzipped of player code, plus the book and its images. A large
  book's codex is repeated per tier, so the export grows with the number of tiers.
