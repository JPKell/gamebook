# ADR 0015: Print layout, signatures and folded sheets

**Status:** Accepted (2026-10-19)

## Context
Authors want control over how the printed book looks: fonts and formatting for every kind
of text, margins with a binding gutter, running headers and footers, and output for
binding. That means signatures of a chosen size, and pages printed two per side on sheets
that are folded.

## Decision
- **The layout lives in the page setup** (`book.print_setup`), next to trim and margins.
  It needs no migration and travels with the git-tree export. Every field has a default,
  and only overridden text-style fields are stored.
- **Styles are roles, not raw CSS.**
  - Each role maps to fixed selectors, and the server generates the CSS.
  - Font names (a restricted character set) and colours (`#rrggbb`) are validated, so
    nothing an author types can reach the stylesheet as code.
  - Generated rules are prefixed with `body` to outrank the base stylesheet.
- **Running heads use CSS paged media.**
  - Margin boxes are set per `:left` and `:right` page. Values come from `string-set`:
    the book title, series and edition from the title page, the act title from act
    headings, and the first or last section number on the page.
  - Pages that shouldn't have heads use a named page (`plain`), or `:first` and `:blank`.
- **Folding fixes the page size.** With `fold` on, the server sets the trim to half the
  sheet, so art sizing, DPI checks and the proof all see the real page.
- **Imposition happens after rendering.** WeasyPrint renders pages in reading order; pypdf
  then pads and lays them out on sheets.
  - The pure arithmetic (`padded_count`, `booklet_sides`) lives in `core/layout.py` and
    is unit-tested.
  - Blanks fill the last signature before the back cover.
  - The export can still produce reading-order pages, for proofing or a printer who
    imposes.
- **Fonts are uploaded files, shared by all books**, at `<data_dir>/fonts/<sha>.<ext>`.
  fontTools validates each file and reads its family, weight and style. Installed fonts
  come from fontconfig, as WeasyPrint uses them.
- **Previews come from a sample PDF**: the front matter, the first sections and a fight,
  rendered on request. It shows exactly what WeasyPrint does, rather than approximating
  it in the browser.

## Consequences
- Folded sheets drop bleed and crop marks: home-printed booklets can't bleed.
- The series git export carries the layout but not the uploaded font files. A layout
  naming a missing font falls back to the default font, and the designer marks it as
  "not installed".
- EPUB ignores the layout: e-readers apply their own fonts.
- Importing WeasyPrint turns on Pillow's `LOAD_TRUNCATED_IMAGES` for the whole process.
  Upload checks now turn it off before decoding, which fixes a Phase 10 hole that let
  truncated images in after any PDF export.
