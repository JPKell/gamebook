# ADR 0012: Print editions, the print compiler and its verifier

**Status:** Accepted (2026-10-18)

## Context
Phase 11 turns a book into a numbered pencil-and-dice gamebook (PDF) and an EPUB. The
engine supports constructs a paper reader can't track on their own:
- text variants chosen by conditions
- `visits()`
- once-only gains
- tier-limited choices

SPEC §8 also left open whether to print one edition per tier or a combined edition.

## Decision
- **One edition per tier.** The tier picks the stats, tests, combat procedure,
  tier-limited choices, the rules chapter and every appendix. A combined edition with
  tier-marked blocks would double the mechanics on every page.
- **Numbering is per act, seeded and stable.**
  - Each act takes a consecutive block of numbers, so act openers and act headings can
    sit at the act's start. Numbers are shuffled within the block using a stored seed.
  - Pins are honoured inside their act's block; the start section is 1.
  - The `section key → number` map is stored, and every number that still fits is kept,
    so adding a section doesn't renumber the book. Only an explicit reshuffle does.
- **Compiling engine features to paper:**
  - **Text variants:** a node with them gets a *router* section: "If …, turn to 57.
    Otherwise, turn to 112." The router sits on the node's own number, so every incoming
    choice still says one number. The engine chooses the variant on arrival, before
    on-entry effects, and the router reads the same state.
  - **`visits()`:** gives the node tick boxes ("tick a box each time you arrive"), and
    conditions read "if you have been to section N before".
  - **Once-only gains and found items** in revisitable nodes get a box and "first box"
    phrasing.
- **The compiler's output is checkable.** Each section carries `links` (choice, outcome
  → number) and `routes` (variant → number), next to the blocks the templates print. The
  verifier plays bots through the engine and requires, at every move:
  - the reader's current section prints that outcome
  - it prints the number the engine went to
  - routers send the reader to the variant the engine chose
  - authored endings print an ending

  This proves compilation preserved every transition the bots took.
- **One set of templates.** Print, the proof and EPUB share Jinja templates with
  per-medium CSS. The PDF comes from WeasyPrint, which loads files only from the asset
  store. The EPUB is written directly (OPF, nav, XHTML via tinyhtml5) rather than with
  ebooklib, which avoids a dependency and keeps the output deterministic.
- **Layout checks need a rendered PDF.** Keep-with and facing-page warnings come from
  WeasyPrint's page anchors after rendering, so they come with the PDF job's result
  rather than the instant pre-flight.

## Consequences
- **Router sections** add one short section per varied node. Variant sections repeat the
  node's mechanics, so a print edition is longer than the node count.
- **Act blocks:** adding sections to an earlier act shifts later acts' blocks, which
  renumbers those acts. Authors who need fixed numbers can pin.
- **The verifier is sampling.** Paths no bot finds aren't proven, and they are listed as
  "not reached". The structural checks still cover every printed link.
- **No HTML-only layout warnings:** "Art can't stay with its section" warnings exist only
  after a PDF build.
