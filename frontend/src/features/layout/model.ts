/** Print layout: types, presets and pure edits (no React). */
import type { components } from '@/api/schema'
import type { PageSetup } from '@/features/art/api'

type S = components['schemas']
export type TextStyle = S['TextStyle']
export type Role = S['RoleOut']
export type RunContent = NonNullable<S['RunningSlots']['left']>
export type Slots = Required<S['RunningSlots']>
export type Line = { verso: Slots; recto: Slots; text: string; gap_mm: number }
export type TitlePage = Required<S['TitlePage']>
export type Sections = Required<S['SectionLayout']>
export type Imposition = Required<S['Imposition']>

/** The page setup with every layout part filled in (the server always sends them). */
export type Layout = Omit<
  PageSetup,
  'header' | 'footer' | 'title_page' | 'sections' | 'imposition' | 'styles'
> & {
  styles: Record<string, TextStyle>
  header: Line
  footer: Line
  title_page: TitlePage
  sections: Sections
  imposition: Imposition
}

const NO_SLOTS: Slots = { left: 'none', center: 'none', right: 'none' }

export function asLayout(p: PageSetup): Layout {
  const line = (l: S['RunningLine'] | undefined): Line => ({
    verso: { ...NO_SLOTS, ...l?.verso },
    recto: { ...NO_SLOTS, ...l?.recto },
    text: l?.text ?? '',
    gap_mm: l?.gap_mm ?? 4,
  })
  return {
    ...p,
    styles: p.styles ?? {},
    header: line(p.header),
    footer: line(p.footer),
    title_page: {
      subtitle: '',
      byline: '',
      show_series: true,
      show_edition: true,
      top_mm: 30,
      ...p.title_page,
    },
    sections: {
      gap_mm: 5,
      divider: 'none',
      keep_together: false,
      hyphenate: true,
      act_break: 'right',
      ...p.sections,
    },
    imposition: {
      fold: false,
      sheet_width_mm: 279.4,
      sheet_height_mm: 215.9,
      signature_pages: 0,
      creep_mm: 0,
      fold_marks: true,
      ...p.imposition,
    },
  }
}

export function layoutBody(l: Layout): S['PageSetup'] {
  const { text_width: _w, text_height: _h, roles: _r, ...rest } = l
  return rest
}

// ── page sizes ───────────────────────────────────────────────────────────

/** Common page and paper sizes, portrait, in mm. */
export const PAGE_SIZES: { key: string; label: string; w: number; h: number; group: string }[] = [
  { key: 'trade6x9', label: 'US Trade 6 × 9 in', w: 152.4, h: 228.6, group: 'Books' },
  { key: 'digest', label: 'Digest 5.5 × 8.5 in', w: 139.7, h: 215.9, group: 'Books' },
  { key: 'novel', label: 'Novel 5 × 8 in', w: 127, h: 203.2, group: 'Books' },
  { key: 'royal', label: 'Royal 6.14 × 9.21 in', w: 156, h: 234, group: 'Books' },
  { key: 'b_format', label: 'B-format 129 × 198 mm', w: 129, h: 198, group: 'Books' },
  { key: 'a_format', label: 'A-format (pocket) 110 × 178 mm', w: 110, h: 178, group: 'Books' },
  { key: 'a4', label: 'A4', w: 210, h: 297, group: 'Paper' },
  { key: 'a5', label: 'A5', w: 148, h: 210, group: 'Paper' },
  { key: 'a6', label: 'A6', w: 105, h: 148, group: 'Paper' },
  { key: 'b5', label: 'B5', w: 176, h: 250, group: 'Paper' },
  { key: 'letter', label: 'US Letter', w: 215.9, h: 279.4, group: 'Paper' },
  { key: 'half_letter', label: 'Half Letter', w: 139.7, h: 215.9, group: 'Paper' },
  { key: 'legal', label: 'US Legal', w: 215.9, h: 355.6, group: 'Paper' },
  { key: 'tabloid', label: 'Tabloid / Ledger', w: 279.4, h: 431.8, group: 'Paper' },
  { key: 'a3', label: 'A3', w: 297, h: 420, group: 'Paper' },
]

const near = (a: number, b: number) => Math.abs(a - b) < 0.6

/** The preset matching a size in either orientation, or null (custom). */
export function matchSize(w: number, h: number): string | null {
  return (
    PAGE_SIZES.find((s) => (near(s.w, w) && near(s.h, h)) || (near(s.w, h) && near(s.h, w)))?.key ??
    null
  )
}

/** The page a folded sheet makes: half the long side by the short side. */
export function foldedPage(sheetW: number, sheetH: number): { w: number; h: number } {
  const long = Math.max(sheetW, sheetH)
  const short = Math.min(sheetW, sheetH)
  return { w: Math.round((long / 2) * 100) / 100, h: Math.round(short * 100) / 100 }
}

// ── signatures ───────────────────────────────────────────────────────────

export const SIGNATURES = [0, 4, 8, 12, 16, 20, 24, 28, 32, 40, 48, 64]

/** Pages after padding to whole signatures (folded: at least whole sheets). */
export function paddedCount(pages: number, imp: Imposition): number {
  const unit = imp.signature_pages || (imp.fold ? 4 : 1)
  return Math.ceil(Math.max(pages, 1) / unit) * unit
}

// ── running heads ────────────────────────────────────────────────────────

export const RUN_CONTENT: { value: RunContent; label: string }[] = [
  { value: 'none', label: '—' },
  { value: 'page', label: 'Page number' },
  { value: 'title', label: 'Book title' },
  { value: 'series', label: 'Series title' },
  { value: 'edition', label: 'Edition' },
  { value: 'act', label: 'Act title' },
  { value: 'section_first', label: 'First section on the page' },
  { value: 'section_last', label: 'Last section on the page' },
  { value: 'text', label: 'Your text' },
]

/** Left-page slots mirrored for the right page (outside stays outside). */
export function mirrored(s: Slots): Slots {
  return { left: s.right, center: s.center, right: s.left }
}

export const LINE_PRESETS: { key: string; label: string; line: Pick<Line, 'verso' | 'recto'> }[] = [
  { key: 'none', label: 'Nothing', line: { verso: NO_SLOTS, recto: NO_SLOTS } },
  {
    key: 'page_center',
    label: 'Page number, centred',
    line: { verso: { ...NO_SLOTS, center: 'page' }, recto: { ...NO_SLOTS, center: 'page' } },
  },
  {
    key: 'page_outside',
    label: 'Page number, outside',
    line: { verso: { ...NO_SLOTS, left: 'page' }, recto: { ...NO_SLOTS, right: 'page' } },
  },
  {
    key: 'sections_outside',
    label: 'Section numbers, outside (gamebook style)',
    line: {
      verso: { ...NO_SLOTS, left: 'section_first' },
      recto: { ...NO_SLOTS, right: 'section_last' },
    },
  },
  {
    key: 'title_act',
    label: 'Book title on left pages, act title on right',
    line: { verso: { ...NO_SLOTS, center: 'title' }, recto: { ...NO_SLOTS, center: 'act' } },
  },
]

// ── text styles ──────────────────────────────────────────────────────────

/** Set one field of a role's style; null clears it (back to the default). */
export function setStyle<K extends keyof TextStyle>(
  styles: Layout['styles'],
  role: string,
  field: K,
  value: TextStyle[K] | null,
): Layout['styles'] {
  const own: Record<string, unknown> = { ...(styles[role] ?? {}) }
  if (value === null || value === undefined || value === '') delete own[field as string]
  else own[field as string] = value
  const next = { ...styles }
  // The API sends unset fields as null: keep only real overrides.
  const kept = Object.fromEntries(Object.entries(own).filter(([, v]) => v != null))
  if (Object.keys(kept).length) next[role] = kept as TextStyle
  else delete next[role]
  return next
}

/** Fields of a role's style that differ from its default. */
export function overrides(styles: Layout['styles'], role: string): string[] {
  return Object.entries(styles[role] ?? {})
    .filter(([, v]) => v != null)
    .map(([k]) => k)
}

/** The style in effect: the default with the overrides on top. */
export function effective(styles: Layout['styles'], role: Role): TextStyle {
  const own = Object.fromEntries(
    Object.entries(styles[role.key] ?? {}).filter(([, v]) => v != null),
  )
  return { ...role.default, ...own }
}
