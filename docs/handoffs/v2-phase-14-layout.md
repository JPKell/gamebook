# v2 Phase 14: Print layout

**Status:** Complete · **Date:** 2026-10-19 · **Branch:** `v2` · **ADR:** 0015 · **SPEC:** §6.3a

## What was built

### Layout model (`core/layout.py`, pure)
- **`TextStyle`:** font, size, line height, bold, italic, small caps, case, alignment,
  colour, letter spacing, space before and after, and indent.
  - **20 roles** (`ROLES`), with defaults (`DEFAULT_STYLES`) that reproduce the Phase 11
    look.
  - Font names and colours are validated.
- **Running heads:** `RunningLine` holds the verso and recto `RunningSlots` (left, centre,
  right), custom text, and the distance from the text.
- **`TitlePage`:** subtitle, author line, show series or edition, and the space above.
- **`SectionLayout`:** gap, divider, keep together, hyphenation, and where acts start.
- **`Imposition`:**
  - fold and sheet size
  - `signature_pages` (a multiple of 4)
  - creep and fold marks
  - `folded_page()`
- **Helpers:**
  - `padded_count`, and `booklet_sides` (the booklet page order)
  - `stylesheet()`: generated CSS for print (paged) or the proof
  - `css_string()`: escapes custom header text

### Page setup (`core/art.py`)
- `PageSetup` gains `gutter_mm`, `styles`, `header`, `footer` (default: page number,
  centred), `title_page`, `sections` and `imposition`.
- `inner_mm` is the margin plus the gutter, and the text width uses it.
- With folding on, a validator sets the trim to half the sheet.
- `PageSetupOut.roles` lists each role's label, description and default.

### Rendering
- `render/print.py` appends the generated stylesheet to print and screen CSS (EPUB is
  unchanged), and passes `tp` (the title page) to `book.html`.
- `print.css`:
  - mirrored margins now use `inner_mm`
  - the hard-coded page number, `.matter .appendix h1` size and title padding have moved
    into the generated CSS
- `services/printing.pdf()` returns `PdfOut`, and takes:
  - `fonts=` (`@font-face` and the fetcher's allowed roots)
  - `imposed=`: padding and folding. Folded sheets render without bleed or crop marks.
  - `sample=`: the front matter, the first 10 sections and the first fight, with dead
    links removed
- The back cover is marked `back_cover` in the parts, so blanks go before it.

### Imposition (`services/imposition.py`)
- pypdf pads to whole signatures.
- When folding, it places two pages per sheet side, with creep and dashed fold marks
  (drawn with pydyf).

### Fonts (`services/fonts.py`)
- `FontStore` at `<data_dir>/fonts`: add (fontTools validates and names the font), list,
  delete, and `faces()`.
- `system_families()` reads fontconfig through `fc-list`.

### API (`api/routers/printing.py`)
- `GET /books/{id}/print/sample?tier&imposed` returns an inline PDF.
- `GET/POST /print/fonts`, `DELETE /print/fonts/{id}`, `GET /print/fonts/{file}`. Files
  are served with CORS for the sandboxed proof.
- `ExportIn.imposed`. A PDF job result adds `blanks`, `sheets` and `signatures`; folded
  output is named `…-sheets.pdf`.

### Frontend
- **`features/layout/`:**
  - `model.ts`: types, page and paper presets, header presets, mirroring, style
    overrides, folding and padding arithmetic
  - `api.ts`: fonts, the sample URL, and `useLayout`, which applies optimistic edits to
    the latest cached value and saves them in order
  - `LayoutPage.tsx`, at `/export/:bookId/layout`:
    - **Tabs:** Page, Text (roles, style editor with live sample text, font manager),
      Headers & footers, Title & sections, Signatures
    - **Preview:** a sample PDF that refreshes after saves, an optional folded-sheet view,
      a spread diagram and the key sizes
- **Export page:** a **Page layout** link; when folding, a choice between folded sheets
  and reading-order pages; the result shows blanks, sheets and signatures.
- **Art → Book:** the page setup panel gains the gutter, disables trim while folding, and
  links to the layout page.

### Fix along the way
Importing WeasyPrint sets Pillow's `LOAD_TRUNCATED_IMAGES` for the whole process. After any
PDF export, the server accepted truncated image uploads. `assets.probe` now turns the flag
off before decoding.

## Bug pass (independent review)
An independent reviewer confirmed 7 findings. All are fixed and covered by tests.
1. **Custom header or footer text could close the inlined `<style>`** and inject markup
   into the PDF. `css_string` now escapes `<` and `>`.
2. **The defaults changed the old look:** the "turn to 1" line lost its centring, and the
   draft note and appendix subheadings changed. Those selectors were dropped from the
   roles, and the subheading default is empty.
3. **The sample PDF kept every later act heading**, giving empty right-hand pages. Acts
   past the cut-off are now dropped.
4. **Number fields sent out-of-range values** (422s), and one bad save could knock later
   edits back.
   - `NumberInput` now keeps to its `min`/`max`, and every layout field declares the
     server's limits.
   - `useLayout` cancels refetches before an optimistic edit, and refetches after an error
     only when no other save is waiting.
5. **Folding a sheet over 1200 × 900 mm returned a 500.** It is now rejected with a 422.
6. **The colour picker saved on every drag tick.** It now saves when the picker closes.
7. **Generic families (`sans-serif`) were quoted**, so browsers didn't treat them as
   generics. They are now left unquoted, in the stylesheet and the style sample.

Also fixed:
- Unknown style roles are dropped, so a setup from a newer version still loads.
- Unfolded padding pages carry the same trim and bleed boxes as the real pages.
- Concurrent uploads of the same font no longer collide on their temp file.
- Font weights round halves up.
- Clearer signature labels when not folding.
- Export can skip signature padding even without folding.

## Tests
- `tests/core/test_layout.py`:
  - roles and defaults; validation (font injection, colours, signatures)
  - the generated CSS: roles, running heads, the proof, section and title options
  - gutter, folding and old setups loading
  - padding and booklet order
- `tests/test_imposition.py`: real PDFs.
  - booklet order on sheets, read by text position
  - blanks before the back cover, several signatures, unfolded padding
  - a no-op, creep direction
- `tests/api/test_layout.py`:
  - page setup round trips, rejections, gutter limits, folding
  - the proof uses the layout; running heads in the PDF
  - signature padding, folded sheets (size and counts) against reading order
  - the sample PDF
  - fonts: upload (a generated TTF), list, reject non-fonts, serve with CORS, path
    safety, the proof's `@font-face`, embedding in the PDF, delete
- `features/layout/model.test.ts`: 8 tests.
- **e2e** (`export.spec.ts`): set a gutter, section style, header preset and folded
  signatures on the layout page, then build `…-sheets.pdf` from Export.

## Known issues / notes
- **Headless browsers show no PDF:** the sample frame relies on the browser's PDF viewer,
  which headless Chromium lacks. The e2e checks the controls and the saved setup instead.
- **Fonts aren't exported:** uploaded fonts belong to the app, not the series, so a series
  zip doesn't carry them.
- **No ligature or OpenType feature controls**, and no two-column layout.
