# v2 Phase 11 — Print & EPUB

**Status:** Complete · **Date:** 2026-10-18 · **Branch:** `v2`

## What was built

### Backend
- **Dependency:** WeasyPrint 70 (PDF). It needs Pango and HarfBuzz, which are already on the deploy host. `tinyhtml5` comes with it and is used for XHTML.
- **Migration 0010:** `book.print_seed` and `book.print_numbers` (the stable section-number map).
- **`core/printbook/numbering.py`:** consecutive per-act blocks, a seeded shuffle, pins (the start is 1), and kept numbers. Pins that can't be honoured are reported.
- **`core/printbook/compile.py`:** book + tier → numbered `Section`s.
  - **Routers:** text variants become a router section plus one section per variant, with a plain fallback if no variant is unconditional.
  - **Tick boxes:**
    - a node used in `visits()` gets as many boxes as its conditions need, up to 5
    - once-only gains and found items in revisitable nodes get a box and "first box" phrasing
  - **Blocks:** effects, found items, shop (stock as boxes), endings.
  - **Choices:** goto (with condition and effects), roll bands, tests (roll, success rule, after-effects), and fights (fixed or table encounters at the edition's stats, flee with cost, lose/no-target phrasing).
  - **Editions:** tier-limited choices are left out of lower editions.
  - **Checkable output:** each section carries `links` and `routes` for the verifier. Warnings cover missing prose, outcomes that lead nowhere, missing tests and dead ends.
- **`core/printbook/verify.py`:** bot games played in the engine, checked move by move against the printed links, routes and endings, plus structural checks. It reports unreached sections.
- **`render/print.py` + `templates/print/`:**
  - `book.html` and `macros.html`, plus three stylesheets:
    - `print.css`: page size from the setup, mirrored margins, bleed, crop marks, recto act openers, full-bleed pages
    - `screen.css`: the proof
    - `epub.css`
  - `creation.html` (character creation).
  - Appendix styles now live in `templates/appendix.css`, shared by previews, the codex, print and EPUB.
- **`services/printing.py`:**
  - numbering persistence and reshuffle
  - compile, using approved prose with beat notes as a marked-draft fallback
  - assigning art to sections by layout
  - front, body and back matter
  - the preview HTML
  - the PDF, with a store-only URL fetcher and keep-with/facing-page warnings from page anchors
  - the EPUB (chunked XHTML, nav, scaled images)
  - preflight, verify and export jobs (the 20 newest kept)
- **API:** `GET /books/{id}/print/preflight|preview`, `POST /books/{id}/print/reshuffle|verify|exports`, `GET /print/exports/{job}`.

### Frontend
- **Export section (`/export/:bookId`):**
  - an edition (tier) picker
  - **Download:** build PDF or EPUB with live job status and a download link. PDF layout warnings are listed, and the git zip is linked.
  - **Pre-flight:** counts of sections, routers, tick boxes and sections without prose; print warnings with section links; artwork problems.
  - **Verify the printed book:** pick a number of games, then see the result.
  - **Section numbers:** the seed, and a reshuffle with a confirmation.
  - **Proof:** the whole edition in a sandboxed iframe; click numbers to follow them, or jump to a section.

## Bug pass (independent review)
The first review attempt was cut off by a usage limit; the resumed review confirmed 9 findings plus nits. All are fixed and covered by regression tests.

1. **Lower editions printed tier-limited effects the engine never applies.** Each effect's `min_tier` was ignored in on-entry effects, choice effects, test after-effects and flee costs. These are now filtered with the engine's rule. `in_edition` matches `Game.tier_allows`: an unknown tier now means hidden, not shown.
2. **A choice with once-only and repeating effects marked all of them "first time only".** A Stamina cost would then be skipped on later visits. The effects are now split: repeating ones print normally, once-only ones get "The first time only, tick ☐ and: …".
3. **Unreachable variants (after an unconditional one) still got section numbers**, leaving gaps in the numbering. Keys and sections now stop at the first unconditional variant.
4. **"Now turn to section 1" was hard-coded.** The begin page now uses the start's real number, and pre-flight warns (`start_not_one`) when another section takes 1.
5. **The verifier only followed the bots' moves.** It now also checks every section against the engine's own rules:
   - routers list the variants in the engine's order, with the fallback
   - the printed choices are exactly the ones the engine offers in this edition
   - the effect counts match what the engine applies, on entry and per choice
   - endings match
   - the begin number is the start's number
   - any authored ending (including dead ends) must print an ending
6. **Every edition's EPUB had the same identifier**, so e-readers would merge them. The identifier is now a uuid5 of the book and tier.
7. **Print numbering was lost on a git export round trip.** `book.yaml` now carries `print_seed` and `print_numbers` (full exports only; undo doesn't rewind numbering).
8. **The EPUB linked images it didn't contain** when a file was missing. Those now become placeholders (hidden in EPUB), with no dangling `<img>`.
9. **A shop item with stock 0 printed as unlimited.** It now prints "Sold out".

Nits also fixed:
- **Table encounters:** a row whose enemies are all unavailable prints "Nothing happens" (the engine counts it as a win). A fixed encounter with nobody to fight says to count it as a win.
- **First-visit wording:** it now names the section holding the tick boxes ("the first box at section N was empty when you arrived").
- **Item lookups** use a dict.
- **The proof's CSP** adds `sandbox`, `frame-ancestors 'self'` and `form-action 'none'`.
- **Verify** is capped at 500 games per request.
- **Proof panel:** "Go to section" moves within the loaded proof without recompiling, and a **Reload** button picks up edits. Download links reset when the edition changes.

Not changed:
- `revisitable()` is a depth-first search from every node: quadratic, but fine at book sizes.
- An act heading can end up in a different EPUB chunk from its first section.

## Tests
- **Backend:** 494, plus 1 opt-in live test.
  - `tests/core/test_print.py` (15, including 6 regressions from the review):
    - numbering: ranges, pins, stability, ignored pins, seeds
    - the router and `visits` ticks
    - first-visit gains
    - per-edition mechanics (tier-limited choices, rolls, tests, fights, flee, shop)
    - the verifier passing a correct book, and catching a wrong number and structural gaps
  - `tests/api/test_print.py` (7, including 3 regressions from the review):
    - numbering stable across new sections, pins, a pin outside the range, reshuffle
    - proof phrasing and CSP
    - the verify endpoint
    - PDF and EPUB exports: the PDF is valid; the EPUB's mimetype comes first and is stored, every XHTML file is well formed, links cross chunks, images and alt text are present
- **Frontend unit:** 59.
- **Browser:** 29. New in `e2e/export.spec.ts`: pre-flight, proof contents, verify, building and downloading the PDF and EPUB.
- **Checked by eye:** a sample PDF, rendered to images.
  - full-bleed cover, title page, character creation, rules, adventure sheet
  - "turn to 1" on its own page
  - numbered sections with a wrapped half-width illustration and a fight table
  - bestiary back matter

## Known issues / notes
- **Act blocks:** adding sections to an earlier act shifts later acts' number blocks (pin numbers that must not move).
- **Variant art:** a node illustration without a variant limit prints in every variant section of that node.
- **Facing pages:** a facing-page placement is placed on a verso before its section. The layout warning tells you when the section doesn't land on the next recto.
- **The verifier samples paths:** sections no bot reached are listed, not proven.
- **No in-app PDF viewer:** the proof is HTML (screen CSS). Exact pagination exists only in the PDF.

## Phase 12 starting points
1. **The game bundle** (`core/engine/bundle.py`) is what the standalone player loads. Add prose, digital art (resized) and the codex appendices, as in SPEC §6.2.
2. **The player UI** can reuse `PlayerExtras` (art, map, codex) and the stateless play model, with the engine compiled to JS or run from the bundle with a small interpreter.
