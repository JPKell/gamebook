# v2 Phase 12 — Standalone digital player

**Status:** Complete · **Date:** 2026-10-19 · **Branch:** `v2`

## What was built

### TypeScript engine (`frontend/src/engine/`)
- **`rational.ts`:** exact BigInt rationals with Python `Fraction` semantics (floor `%`, floor and ceil).
- **gbx (`gbx/`):**
  - `pcg32.ts`: PCG32 dice, identical to `SeededRng`.
  - `parse.ts`: the lexer and Pratt parser, with the same grammar, limits and error messages.
  - `evaluate.ts`: the compiled path's semantics (Python `==`, short-circuiting, rounding, the same errors).
- **`rules.ts`:** `effectiveTier`.
- **`model.ts`:** bundle types, `readBundle`.
- **`game.ts`:** the engine (state, effects, once-only effects, variants, choices, tests, rolls, encounters and tables, combat with hooks, flee, defeat, items, shop), plus `stateToDict`.
- **`narrate.ts`:** event narration.
- **`trace.ts`:** replay.
- **Parity:**
  - `parity.test.ts` replays the six golden traces with full event diffs.
  - It also replays `__fixtures__/parity.json`: 48 bot games across tiers and seeds on the engine book, plus an "edge" book with content errors (unknown names, division by zero, bad syntax, negative `%`). These are compared by final state and an event SHA-256.
  - The fixture comes from `backend/tests/core/parity_corpus.py`. `tests/core/test_parity_corpus.py` fails when the Python engine changes without regenerating it (`uv run python -m tests.core.parity_corpus`).

### Web player
- **Build:** `vite.player.config.ts` + `player.html` → `frontend/dist-player/`, one classic script (IIFE) with relative paths. `npm run build` / `make build` builds it alongside the app; `make clean` removes it.
- **`src/player/`:**
  - **`Root.tsx`:** the embedded book, or a file picker in development.
  - **`App.tsx`:**
    - Title screen: cover, edition, class, saves.
    - Play screen: art by variant and tier with zoom; prose, or draft notes; what happened; combat; choices (disabled ones with their reasons); item and shop actions; endings; Back; Save; Menu.
    - Sidebar: adventure sheet, maps (`visible_if` markers, you-are-here), and a codex in a sandboxed frame with CSS-injected unlocks.
  - **`saves.ts`:** an autosave plus up to 20 named `localStorage` slots of `{tier, seed, class, moves}`, robust to blocked or corrupt storage.
  - **`useGame.ts`:** replay.
  - **`met.ts`:** what the reader has met.
  - **`player.css`:** light and dark themes, phone-friendly.
  - **`main.tsx`:** registers the service worker over http(s).

### Backend
- **`services/web_player.py`:** builds the zip.
  - The player app, with `index.html` rewritten to classic deferred scripts without `crossorigin` (so it runs from `file://`) and given the book's title.
  - `book.js` (`window.GAMEBOOK`, format `gamebook-player` v1): the game bundle; approved prose; beat notes for unwritten sections; digital art scaled to 1600 px; the cover; maps; and per-tier codex documents. The adventure sheet and maps appendices are left out, because the player shows those itself.
  - `manifest.webmanifest`, `icon.svg`, and `sw.js` with a cache versioned by content hash.
- **Export job:** format `web` (`ExportIn.format`); the download is `<book>-web.zip`.
- **Settings:** `player_dist` (default: next to `frontend_dist`, else the repository's `frontend/dist-player`).
- **Appendix templates:** bestiary and item entries carry `data-enemy` / `data-item` keys; item entries carry `key`.

### Frontend app
- The Export page has **Build web player**, with a note on how to use the zip.

## Bug pass (independent review)
An independent reviewer confirmed 8 findings plus nits. All are fixed and covered by regression tests.

1. **A save from an older edition froze the game.** Replay stopped at a move the book no longer had, and every new move was appended after it. Opening a save now checks it against the book, drops the moves that no longer apply, says so, and continues from there.
2. **A stale or damaged slot crashed the player to a blank page.** For example, a tier or class the book no longer has, or a slot with no moves. Such saves are now refused with a message, storage entries are checked before use, and an error boundary offers "Back to the start".
3. **The service worker deleted other books' offline caches on the same site.** Caches are now named `gamebook-<book>-<version>` and only this book's old ones are removed.
4. **Unicode digits and spaces tokenised differently** (Python's `\d`/`\s` are Unicode, JS's aren't). Both lexers are now ASCII-only (`re.ASCII` in Python, `[ \t\n\r\f\v]` in TS), and error text for control characters matches Python's `repr`.
5. **Large numbers lost precision or crashed the player.** TS literals are now exact BigInts. Both engines reject integer results beyond 2^53 with "number too large", so the player can't overflow a double, and the corpus pins both cases.
6. **The Python reference engine was nondeterministic.** It iterated effective stats over a frozenset, so error events could come out in any order. Stats are now iterated in definition order.
7. **TS stat and formula lookups could hit `Object.prototype`** (keys like `constructor`). Lookups now check own keys only.
8. **Rendering the sheet logged errors into the game's event log.** `peekStats()` now evaluates quietly for display.

Nits also fixed:
- Notes now cover any section version without prose, not just wholly unwritten sections.
- Autosave runs only after a move, so starting or loading never overwrites it.
- The codex CSS injection uses a function replacer and full escaping.
- The lightbox closes with Escape and moves focus.
- The "What happened" live region stays mounted between moves.
- Map pins are `aria-hidden`; markers without a label read "Marked place".
- Figures are keyed by index, so the same image placed twice works.
- Invalid seeds in storage are rejected.
- The service worker caches files one by one, so a host without a directory index still installs it.
- `favicon.svg` is no longer shipped (`publicDir: false`).
- The web export button no longer waits for a tier.
- Error, setup and dice lines are hidden from readers' narration.

## Tests
- **Backend:** 499, plus 1 opt-in live test.
  - `tests/api/test_web_player.py`:
    - zip structure, script rewriting, book data (bundle, prose, digital-only art scaled, maps, codex per tier, no sheet, entry keys)
    - the service worker and manifest
    - a failed export without a player build
  - `tests/core/test_parity_corpus.py`.
- **Frontend unit:** 129.
  - `engine/parity.test.ts`: 6 golden traces, 48 corpus games, the PCG32 stream.
  - `engine/engine.test.ts`: rationals, parsing and error messages, evaluation, dice, big integers, ASCII-only tokens, prototype keys.
  - `player/player.test.ts`: replaying saves, moves that no longer apply, met tracking, save slots, opening stale saves, damaged storage.
- **Browser:** 30. New in `e2e/player.spec.ts`:
  - build the web player on the Export page, download and unzip it, then open it from `file://`
  - begin, save, fight to an ending, and go back a step
  - reload; the saves are listed, and loading one restores the game

## Known issues / notes
- **Engine changes cost twice:** regenerate the corpus, then make the TS engine pass.
- **Saves and edited books:** a save replays only as far as its moves still fit an edited book.
- **The codex is per tier:** it is repeated for every tier, which grows the export for books with many tiers and appendices.
- **No debug tools** (jump, set, force rolls) in the reader. Those stay in the authoring app's player.

## What's next
PLAN's numbered phases are done. Deferred items (PLAN "Later"):
- cross-book carry-over
- combined print editions
- a mobile wrapper
- multi-user
