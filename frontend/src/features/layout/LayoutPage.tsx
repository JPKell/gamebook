import { ArrowLeft, FlipHorizontal2, RefreshCw, RotateCcw, Trash2, Upload } from 'lucide-react'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { useBook } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Checkbox, NumberInput, Select, TextInput } from '@/components/ui/inputs'
import { Tabs } from '@/components/ui/tabs'
import { Panel } from '@/features/entities/EntityHeader'
import { useSeriesVocab } from '@/features/entities/useSeriesVocab'
import { cn } from '@/lib/utils'

import { type Fonts, sampleUrl, useDeleteFont, useFonts, useLayout, useUploadFont } from './api'
import {
  effective,
  foldedPage,
  type Layout,
  type Line,
  LINE_PRESETS,
  matchSize,
  mirrored,
  overrides,
  PAGE_SIZES,
  type Role,
  RUN_CONTENT,
  type RunContent,
  setStyle,
  SIGNATURES,
  type Slots,
  type TextStyle,
} from './model'

type Update = (fn: (l: Layout) => Layout) => void

/** The print layout designer: page, text styles, running heads, sections, signatures. */
export function LayoutPage() {
  const { bookId = '' } = useParams()
  const book = useBook(bookId)
  const vocab = useSeriesVocab(book.data?.series_id ?? '')
  const { layout, update, save, error } = useLayout(bookId)
  const [tab, setTab] = useState('page')
  const [tier, setTier] = useState<string | null>(null)
  const edition = tier ?? vocab.tiers[vocab.tiers.length - 1]?.key ?? null
  return (
    <div className="mx-auto flex h-full max-w-[1500px] flex-col gap-4 px-6 py-6">
      <header className="flex flex-wrap items-center gap-3">
        <Link
          to={`/export/${bookId}`}
          className="flex items-center gap-1 text-sm text-muted hover:text-text"
        >
          <ArrowLeft className="size-4" /> Export
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">Page layout</h1>
        <span className="text-muted">{book.data?.title}</span>
        <span className="ml-auto text-xs text-muted" role="status">
          {save.isPending ? 'Saving…' : save.error ? '' : layout ? 'Saved' : ''}
        </span>
        <Select
          aria-label="Edition"
          value={edition}
          options={vocab.tiers.map((t) => ({ value: t.key, label: `${t.label} edition` }))}
          onValueChange={(t) => t && setTier(t)}
          className="w-auto"
        />
      </header>
      {(error || save.error) && (
        <p role="alert" className="text-sm text-danger">
          {(error ?? save.error)?.message}
        </p>
      )}
      {layout && (
        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[540px_minmax(0,1fr)]">
          <div className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-surface">
            <Tabs
              value={tab}
              onValueChange={setTab}
              tabs={[
                { value: 'page', label: 'Page', content: <PageTab l={layout} update={update} /> },
                { value: 'text', label: 'Text', content: <TextTab l={layout} update={update} /> },
                {
                  value: 'running',
                  label: 'Headers & footers',
                  content: <RunningTab l={layout} update={update} />,
                },
                {
                  value: 'sections',
                  label: 'Title & sections',
                  content: <SectionsTab l={layout} update={update} />,
                },
                {
                  value: 'printing',
                  label: 'Signatures',
                  content: <PrintingTab l={layout} update={update} />,
                },
              ]}
              className="min-h-0 flex-1"
            />
          </div>
          <Preview bookId={bookId} tier={edition} l={layout} saving={save.isPending} />
        </div>
      )}
    </div>
  )
}

// ── preview ──────────────────────────────────────────────────────────────

function Preview({
  bookId,
  tier,
  l,
  saving,
}: {
  bookId: string
  tier: string | null
  l: Layout
  saving: boolean
}) {
  const [sheets, setSheets] = useState(false)
  const [version, setVersion] = useState(0)
  const [auto, setAuto] = useState(true)
  // Re-render the sample a moment after the last save lands.
  const stamp = JSON.stringify(l)
  const first = useRef(true)
  useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    if (!auto || saving) return
    const t = setTimeout(() => setVersion((v) => v + 1), 900)
    return () => clearTimeout(t)
  }, [stamp, saving, auto])
  const imposed = sheets && l.imposition.fold
  const src = `${sampleUrl(bookId, tier, imposed)}&v=${version}`
  return (
    <section
      aria-label="Layout preview"
      className="flex min-h-[70vh] flex-col overflow-hidden rounded-xl border border-border"
    >
      <div className="flex flex-wrap items-center gap-3 border-b border-border bg-surface px-3 py-2 text-sm">
        <span className="font-medium">Sample</span>
        <span className="text-xs text-muted">Front matter and the first sections, as printed.</span>
        <div className="ml-auto flex items-center gap-3">
          {l.imposition.fold && (
            <Checkbox checked={sheets} onCheckedChange={setSheets} label="Folded sheets" />
          )}
          <Checkbox checked={auto} onCheckedChange={setAuto} label="Auto-refresh" />
          <Button size="sm" variant="ghost" onClick={() => setVersion((v) => v + 1)}>
            <RefreshCw className="size-4" /> Refresh
          </Button>
        </div>
      </div>
      <div className="grid min-h-0 flex-1 xl:grid-cols-[minmax(0,1fr)_220px]">
        {tier && (
          <iframe
            key={src}
            title="Layout sample"
            src={src}
            className="h-full min-h-[60vh] w-full bg-white"
          />
        )}
        <div className="hidden space-y-3 border-l border-border bg-surface p-3 xl:block">
          <SpreadDiagram l={l} />
          <Facts l={l} />
        </div>
      </div>
    </section>
  )
}

function Facts({ l }: { l: Layout }) {
  const rows: [string, string][] = [
    ['Page', `${l.trim_width_mm} × ${l.trim_height_mm} mm`],
    ['Text block', `${l.text_width} × ${l.text_height} mm`],
    ['Inner margin', `${l.margin_inner_mm + l.gutter_mm} mm (gutter ${l.gutter_mm})`],
  ]
  if (l.imposition.fold)
    rows.push([
      'Sheet',
      `${Math.max(l.imposition.sheet_width_mm, l.imposition.sheet_height_mm)} × ${Math.min(l.imposition.sheet_width_mm, l.imposition.sheet_height_mm)} mm, 4 pages`,
    ])
  if (l.imposition.signature_pages || l.imposition.fold)
    rows.push([
      'Signature',
      l.imposition.signature_pages ? `${l.imposition.signature_pages} pages` : 'whole book',
    ])
  return (
    <dl className="space-y-1 text-xs">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt className="text-muted">{k}</dt>
          <dd className="tabular-nums">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

/** Two facing pages: margins, the gutter against the spine, the text block and running heads. */
export function SpreadDiagram({ l }: { l: Layout }) {
  const W = l.trim_width_mm
  const H = l.trim_height_mm
  const inner = l.margin_inner_mm + l.gutter_mm
  const tw = Math.max(5, W - inner - l.margin_outer_mm)
  const th = Math.max(5, H - l.margin_top_mm - l.margin_bottom_mm)
  const page = (x: number, verso: boolean) => {
    const left = verso ? x + l.margin_outer_mm : x + inner
    const gutterX = verso ? x + W - l.gutter_mm : x
    const head = verso ? l.header.verso : l.header.recto
    const foot = verso ? l.footer.verso : l.footer.recto
    const marks = (s: Slots, y: number) =>
      (['left', 'center', 'right'] as const)
        .filter((k) => s[k] !== 'none')
        .map((k) => {
          const w = Math.min(18, tw / 3)
          const mx = k === 'left' ? left : k === 'right' ? left + tw - w : left + (tw - w) / 2
          return <rect key={k} x={mx} y={y} width={w} height={1.6} fill="var(--muted)" />
        })
    return (
      <g key={x}>
        <rect
          x={x}
          y={0}
          width={W}
          height={H}
          fill="var(--bg)"
          stroke="var(--border)"
          strokeWidth={0.8}
        />
        {l.gutter_mm > 0 && (
          <rect
            x={gutterX}
            y={0}
            width={l.gutter_mm}
            height={H}
            fill="var(--warning)"
            fillOpacity={0.15}
          />
        )}
        <rect
          x={left}
          y={l.margin_top_mm}
          width={tw}
          height={th}
          fill="var(--accent)"
          fillOpacity={0.08}
          stroke="var(--accent)"
          strokeDasharray="1.5 1.5"
          strokeWidth={0.4}
        />
        {marks(head, l.margin_top_mm - l.header.gap_mm - 2)}
        {marks(foot, H - l.margin_bottom_mm + l.footer.gap_mm + 0.5)}
      </g>
    )
  }
  return (
    <svg
      viewBox={`-2 -2 ${2 * W + 4} ${H + 4}`}
      role="img"
      aria-label={`Spread: pages ${W} × ${H} mm, text block ${Math.round(tw)} × ${Math.round(th)} mm, gutter ${l.gutter_mm} mm`}
      className="w-full"
    >
      {page(0, true)}
      {page(W, false)}
      <line x1={W} x2={W} y1={0} y2={H} stroke="var(--text)" strokeWidth={0.6} />
    </svg>
  )
}

// ── shared bits ──────────────────────────────────────────────────────────

function Section({
  title,
  hint,
  children,
}: {
  title: string
  hint?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {hint && <p className="text-xs text-muted">{hint}</p>}
      {children}
    </div>
  )
}

function Mm({
  label,
  value,
  onCommit,
  hint,
  disabled,
  step = 0.5,
  unit = 'mm',
  min = 0,
  max,
}: {
  label: string
  value: number
  onCommit: (v: number) => void
  hint?: string
  disabled?: boolean
  step?: number
  unit?: string
  min?: number
  max: number
}) {
  return (
    <Field label={`${label} (${unit})`} hint={hint}>
      {(id) => (
        <NumberInput
          id={id}
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onCommit={(v) => v !== null && onCommit(v)}
        />
      )}
    </Field>
  )
}

// ── page ─────────────────────────────────────────────────────────────────

function PageTab({ l, update }: { l: Layout; update: Update }) {
  const folded = l.imposition.fold
  const size = matchSize(l.trim_width_mm, l.trim_height_mm)
  const set = (patch: Partial<Layout>) => update((x) => ({ ...x, ...patch }))
  return (
    <div className="space-y-6">
      <Section
        title="Page size"
        hint={
          folded
            ? 'Set by the folded sheet: half of it (see Signatures).'
            : 'The trimmed page. Choose a preset or type a size.'
        }
      >
        <Select
          aria-label="Page size"
          disabled={folded}
          value={size ?? 'custom'}
          options={[
            ...PAGE_SIZES.map((s) => ({ value: s.key, label: s.label, group: s.group })),
            { value: 'custom', label: 'Custom', group: 'Other' },
          ]}
          onValueChange={(k) => {
            const s = PAGE_SIZES.find((p) => p.key === k)
            if (s) set({ trim_width_mm: s.w, trim_height_mm: s.h })
          }}
        />
        <div className="grid grid-cols-[1fr_1fr_auto] items-end gap-3">
          <Mm
            min={50}
            max={600}
            label="Width"
            value={l.trim_width_mm}
            disabled={folded}
            onCommit={(v) => set({ trim_width_mm: v })}
          />
          <Mm
            min={50}
            max={900}
            label="Height"
            value={l.trim_height_mm}
            disabled={folded}
            onCommit={(v) => set({ trim_height_mm: v })}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={folded}
            aria-label="Swap width and height"
            onClick={() =>
              set({ trim_width_mm: l.trim_height_mm, trim_height_mm: l.trim_width_mm })
            }
          >
            <FlipHorizontal2 className="size-4" />
          </Button>
        </div>
      </Section>
      <Section
        title="Margins"
        hint="Inner margins sit against the spine; the gutter adds space there for the binding."
      >
        <div className="grid grid-cols-2 gap-3">
          <Mm
            max={100}
            label="Top"
            value={l.margin_top_mm}
            onCommit={(v) => set({ margin_top_mm: v })}
          />
          <Mm
            max={100}
            label="Bottom"
            value={l.margin_bottom_mm}
            onCommit={(v) => set({ margin_bottom_mm: v })}
          />
          <Mm
            max={100}
            label="Inner"
            value={l.margin_inner_mm}
            onCommit={(v) => set({ margin_inner_mm: v })}
          />
          <Mm
            max={100}
            label="Outer"
            value={l.margin_outer_mm}
            onCommit={(v) => set({ margin_outer_mm: v })}
          />
          <Mm
            max={50}
            label="Gutter"
            value={l.gutter_mm}
            hint="Extra inner margin for the binding"
            onCommit={(v) => set({ gutter_mm: v })}
          />
          <Mm
            max={20}
            label="Bleed"
            value={l.bleed_mm}
            hint={folded ? 'Not used on folded sheets' : 'Beyond the trim, for full-page art'}
            onCommit={(v) => set({ bleed_mm: v })}
          />
        </div>
        <p className="text-xs text-muted">
          Text block {l.text_width} × {l.text_height} mm.
        </p>
      </Section>
      <div className="xl:hidden">
        <SpreadDiagram l={l} />
      </div>
    </div>
  )
}

// ── text styles ──────────────────────────────────────────────────────────

/** The server's limits for style numbers. */
const STYLE_LIMITS = {
  size_pt: [4, 96],
  line_height: [0.8, 3],
  letter_spacing_em: [-0.1, 0.5],
  space_before_mm: [0, 80],
  space_after_mm: [0, 80],
  indent_mm: [0, 30],
} as const

const GENERIC = ['serif', 'sans-serif', 'monospace']
const fontStack = (f: string) => (GENERIC.includes(f) ? f : `"${f}", serif`)

const TRI = [
  { value: 'default', label: 'Default' },
  { value: 'on', label: 'On' },
  { value: 'off', label: 'Off' },
] as const

function TextTab({ l, update }: { l: Layout; update: Update }) {
  const roles = l.roles
  const [roleKey, setRoleKey] = useState('body')
  const role = roles.find((r) => r.key === roleKey) ?? roles[0]
  const fonts = useFonts()
  if (!role) return null
  const changed = (k: string) => overrides(l.styles, k).length > 0
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-[160px_minmax(0,1fr)] gap-4">
        <ul aria-label="Text roles" className="space-y-0.5">
          {roles.map((r) => (
            <li key={r.key}>
              <button
                type="button"
                onClick={() => setRoleKey(r.key)}
                aria-current={r.key === role.key}
                className={cn(
                  'flex w-full items-center gap-1 rounded-md px-2 py-1 text-left text-sm hover:bg-surface-2',
                  r.key === role.key && 'bg-surface-2 font-medium text-accent',
                )}
              >
                <span className="min-w-0 flex-1 truncate">{r.label}</span>
                {changed(r.key) && (
                  <span className="size-1.5 rounded-full bg-accent" aria-label="changed" />
                )}
              </button>
            </li>
          ))}
        </ul>
        <StyleEditor
          key={role.key}
          role={role}
          styles={l.styles}
          fonts={fonts.data}
          bodyFont={l.styles.body?.font ?? null}
          onChange={(field, value) =>
            update((x) => ({ ...x, styles: setStyle(x.styles, role.key, field, value) }))
          }
          onReset={() =>
            update((x) => {
              const styles = { ...x.styles }
              delete styles[role.key]
              return { ...x, styles }
            })
          }
        />
      </div>
      <FontManager fonts={fonts.data} />
    </div>
  )
}

function StyleEditor({
  role,
  styles,
  fonts,
  bodyFont,
  onChange,
  onReset,
}: {
  role: Role
  styles: Layout['styles']
  fonts: Fonts | undefined
  bodyFont: string | null
  onChange: <K extends keyof TextStyle>(field: K, value: TextStyle[K] | null) => void
  onReset: () => void
}) {
  const own = styles[role.key] ?? {}
  const eff = effective(styles, role)
  const d = role.default
  const box = role.key === 'header' || role.key === 'footer'
  const inherited =
    role.key === 'body' ? 'Default (Georgia, serif)' : `Default (${bodyFont ?? 'as body text'})`
  const families = new Set<string>()
  const fontOptions: { value: string; label: string; group?: string }[] = []
  for (const f of fonts?.uploaded ?? [])
    if (!families.has(f.family)) {
      families.add(f.family)
      fontOptions.push({ value: f.family, label: f.family, group: 'Uploaded' })
    }
  for (const f of fonts?.system ?? [])
    if (!families.has(f)) {
      families.add(f)
      fontOptions.push({ value: f, label: f, group: 'Installed' })
    }
  for (const f of fonts?.generic ?? []) fontOptions.push({ value: f, label: f, group: 'Generic' })
  if (own.font && !fontOptions.some((o) => o.value === own.font))
    fontOptions.push({ value: own.font, label: `${own.font} (not installed)`, group: 'Missing' })
  const tri = (v: boolean | null | undefined) => (v == null ? 'default' : v ? 'on' : 'off')
  const fromTri = (v: string | null) => (v === 'on' ? true : v === 'off' ? false : null)
  const num = (field: keyof typeof STYLE_LIMITS, label: string, step: number) => (
    <Field label={label}>
      {(id) => (
        <NumberInput
          id={id}
          allowEmpty
          step={step}
          min={STYLE_LIMITS[field][0]}
          max={STYLE_LIMITS[field][1]}
          value={own[field] ?? null}
          placeholder={d[field] != null ? String(d[field]) : 'inherit'}
          onCommit={(v) => onChange(field, v)}
        />
      )}
    </Field>
  )
  return (
    <div className="min-w-0 space-y-3">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold">{role.label}</h3>
          <p className="text-xs text-muted">{role.description}</p>
        </div>
        <Button
          size="sm"
          variant="ghost"
          disabled={overrides(styles, role.key).length === 0}
          onClick={onReset}
        >
          <RotateCcw className="size-4" /> Reset
        </Button>
      </div>
      <p
        aria-label="Sample"
        className="rounded-md border border-border bg-white px-3 py-2 text-black"
        style={{
          fontFamily: eff.font ? fontStack(eff.font) : undefined,
          fontSize: eff.size_pt ? `${eff.size_pt}pt` : undefined,
          lineHeight: eff.line_height ?? undefined,
          fontWeight: eff.bold ? 700 : undefined,
          fontStyle: eff.italic ? 'italic' : undefined,
          fontVariant: eff.small_caps ? 'small-caps' : undefined,
          textTransform:
            eff.case === 'upper'
              ? 'uppercase'
              : eff.case === 'lower'
                ? 'lowercase'
                : eff.case === 'capitalize'
                  ? 'capitalize'
                  : undefined,
          textAlign: box ? undefined : (eff.align ?? undefined),
          color: eff.color ?? undefined,
          letterSpacing: eff.letter_spacing_em != null ? `${eff.letter_spacing_em}em` : undefined,
        }}
      >
        {role.key === 'section'
          ? '217'
          : role.key === 'turn'
            ? '42'
            : 'The lantern gutters as you turn to 42.'}
      </p>
      <Field label="Font">
        {(id) => (
          <Select
            id={id}
            value={own.font ?? null}
            placeholder={inherited}
            options={fontOptions}
            onValueChange={(v) => onChange('font', v)}
          />
        )}
      </Field>
      <div className="grid grid-cols-2 gap-3">
        {num('size_pt', 'Size (pt)', 0.5)}
        {num('line_height', 'Line height', 0.05)}
      </div>
      <div className="space-y-1.5">
        {(
          [
            ['bold', 'Bold'],
            ['italic', 'Italic'],
            ['small_caps', 'Small caps'],
          ] as const
        ).map(([field, label]) => (
          <Field
            key={field}
            inline
            className="[&>label]:w-40"
            label={`${label}${d[field] != null ? ` (default ${d[field] ? 'on' : 'off'})` : ''}`}
          >
            {(id) => (
              <Select
                id={id}
                value={tri(own[field])}
                options={[...TRI]}
                onValueChange={(v) => onChange(field, fromTri(v))}
              />
            )}
          </Field>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label={`Case${d.case ? ` (default ${d.case})` : ''}`}>
          {(id) => (
            <Select
              id={id}
              value={own.case ?? null}
              placeholder="Default"
              options={[
                { value: 'none', label: 'As written' },
                { value: 'upper', label: 'UPPER CASE' },
                { value: 'lower', label: 'lower case' },
                { value: 'capitalize', label: 'Capitalise Each Word' },
              ]}
              onValueChange={(v) => onChange('case', v)}
            />
          )}
        </Field>
        {!box && (
          <Field label={`Alignment${d.align ? ` (default ${d.align})` : ''}`}>
            {(id) => (
              <Select
                id={id}
                value={own.align ?? null}
                placeholder="Default"
                options={[
                  { value: 'left', label: 'Left' },
                  { value: 'center', label: 'Centre' },
                  { value: 'right', label: 'Right' },
                  { value: 'justify', label: 'Justified' },
                ]}
                onValueChange={(v) => onChange('align', v)}
              />
            )}
          </Field>
        )}
        <Field label="Colour">
          {(id) => (
            <div className="flex items-center gap-2">
              <ColorInput
                id={id}
                value={eff.color ?? '#111111'}
                onCommit={(v) => onChange('color', v)}
              />
              <span className="font-mono text-xs text-muted">{eff.color ?? 'inherit'}</span>
              {own.color && (
                <Button size="sm" variant="ghost" onClick={() => onChange('color', null)}>
                  Default
                </Button>
              )}
            </div>
          )}
        </Field>
        {num('letter_spacing_em', 'Letter spacing (em)', 0.01)}
        {!box && num('space_before_mm', 'Space before (mm)', 0.5)}
        {!box && num('space_after_mm', 'Space after (mm)', 0.5)}
        {!box &&
          num(
            'indent_mm',
            role.key === 'body' ? 'Paragraph indent (mm)' : 'First-line indent (mm)',
            0.5,
          )}
      </div>
      {box && (
        <p className="text-xs text-muted">
          What the {role.key} shows, and its distance from the text, are on the Headers &amp;
          footers tab.
        </p>
      )}
    </div>
  )
}

/** A colour picker that saves once a colour is chosen, not on every drag. */
function ColorInput({
  id,
  value,
  onCommit,
}: {
  id: string
  value: string
  onCommit: (v: string) => void
}) {
  const [draft, setDraft] = useState(value)
  const [seen, setSeen] = useState(value)
  if (value !== seen) {
    setSeen(value)
    setDraft(value)
  }
  const ref = useRef<HTMLInputElement>(null)
  const latest = useRef({ value, onCommit })
  useEffect(() => {
    latest.current = { value, onCommit }
  })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    // The native "change" event fires when the picker closes (React's onChange is "input").
    const commit = () => {
      if (el.value !== latest.current.value) latest.current.onCommit(el.value)
    }
    el.addEventListener('change', commit)
    return () => el.removeEventListener('change', commit)
  }, [])
  return (
    <input
      ref={ref}
      id={id}
      type="color"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      className="h-8 w-12 cursor-pointer rounded border border-border bg-bg"
    />
  )
}

function FontManager({ fonts }: { fonts: Fonts | undefined }) {
  const upload = useUploadFont()
  const remove = useDeleteFont()
  const input = useRef<HTMLInputElement>(null)
  return (
    <Panel
      title="Fonts"
      aside={
        <>
          <input
            ref={input}
            type="file"
            accept=".ttf,.otf,.woff,.woff2,font/ttf,font/otf,font/woff,font/woff2"
            multiple
            hidden
            aria-label="Font files"
            onChange={async (e) => {
              const files = [...(e.target.files ?? [])]
              e.target.value = ''
              for (const f of files) await upload.mutateAsync(f).catch(() => undefined)
            }}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={upload.isPending}
            onClick={() => input.current?.click()}
          >
            <Upload className="size-4" /> {upload.isPending ? 'Uploading…' : 'Upload fonts'}
          </Button>
        </>
      }
    >
      <p className="text-xs text-muted">
        TrueType, OpenType or WOFF files; upload each weight and style you use (regular, bold,
        italic). Fonts are embedded in the PDF. Make sure their licences allow it.
      </p>
      {upload.error && <p className="text-xs text-danger">{upload.error.message}</p>}
      {fonts?.uploaded.length ? (
        <ul className="space-y-1 text-sm">
          {fonts.uploaded.map((f) => (
            <li key={f.id} className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate" style={{ fontFamily: `"${f.family}"` }}>
                {f.family}
              </span>
              <span className="text-xs text-muted">
                {f.weight}
                {f.italic ? ' italic' : ''}
              </span>
              <Button
                size="sm"
                variant="ghost"
                aria-label={`Delete ${f.family} ${f.weight}${f.italic ? ' italic' : ''}`}
                onClick={() => {
                  if (
                    window.confirm(
                      `Delete this ${f.family} file? Layouts using it fall back to the default font.`,
                    )
                  )
                    remove.mutate(f.id)
                }}
              >
                <Trash2 className="size-4" />
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted">
          No uploads yet. {fonts?.system.length ?? 0} installed families are available.
        </p>
      )}
    </Panel>
  )
}

// ── headers & footers ────────────────────────────────────────────────────

function RunningTab({ l, update }: { l: Layout; update: Update }) {
  return (
    <div className="space-y-6">
      <p className="text-xs text-muted">
        Left pages are versos (even), right pages rectos (odd). The title page, art pages and blank
        pages have none. Fonts for these are on the Text tab.
      </p>
      <LineEditor name="Header" which="header" l={l} update={update} />
      <LineEditor name="Footer" which="footer" l={l} update={update} />
    </div>
  )
}

function LineEditor({
  name,
  which,
  l,
  update,
}: {
  name: string
  which: 'header' | 'footer'
  l: Layout
  update: Update
}) {
  const line = l[which]
  const set = (fn: (line: Line) => Line) => update((x) => ({ ...x, [which]: fn(x[which]) }))
  const usesText = [...Object.values(line.verso), ...Object.values(line.recto)].includes('text')
  const preset = LINE_PRESETS.find(
    (p) => JSON.stringify(p.line) === JSON.stringify({ verso: line.verso, recto: line.recto }),
  )
  return (
    <Section title={name}>
      <Select
        aria-label={`${name} preset`}
        value={preset?.key ?? null}
        placeholder="Custom"
        options={LINE_PRESETS.map((p) => ({ value: p.key, label: p.label }))}
        onValueChange={(k) => {
          const p = LINE_PRESETS.find((x) => x.key === k)
          if (p) set((ln) => ({ ...ln, ...p.line }))
        }}
      />
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-muted">
            <th className="w-24 text-left font-medium"></th>
            <th className="text-left font-medium">Left</th>
            <th className="text-left font-medium">Centre</th>
            <th className="text-left font-medium">Right</th>
          </tr>
        </thead>
        <tbody>
          {(['verso', 'recto'] as const).map((side) => (
            <tr key={side}>
              <td className="pr-2 text-xs text-muted">
                {side === 'verso' ? 'Left page' : 'Right page'}
              </td>
              {(['left', 'center', 'right'] as const).map((slot) => (
                <td key={slot} className="p-0.5">
                  <Select
                    aria-label={`${name}, ${side === 'verso' ? 'left' : 'right'} page, ${slot}`}
                    value={line[side][slot]}
                    options={RUN_CONTENT}
                    onValueChange={(v) =>
                      set((ln) => ({
                        ...ln,
                        [side]: { ...ln[side], [slot]: (v ?? 'none') as RunContent },
                      }))
                    }
                    className="px-1.5 text-xs"
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex flex-wrap items-end gap-3">
        <Button
          size="sm"
          variant="outline"
          onClick={() => set((ln) => ({ ...ln, recto: mirrored(ln.verso) }))}
        >
          <FlipHorizontal2 className="size-4" /> Mirror left page onto right
        </Button>
        <div className="w-36">
          <Mm
            max={40}
            label="Distance from text"
            value={line.gap_mm}
            onCommit={(v) => set((ln) => ({ ...ln, gap_mm: v }))}
          />
        </div>
      </div>
      {usesText && (
        <Field label="Your text">
          {(id) => (
            <TextInput
              id={id}
              value={line.text}
              maxLength={120}
              onCommit={(v) => set((ln) => ({ ...ln, text: v }))}
            />
          )}
        </Field>
      )}
    </Section>
  )
}

// ── title page & sections ────────────────────────────────────────────────

function SectionsTab({ l, update }: { l: Layout; update: Update }) {
  const tp = l.title_page
  const sec = l.sections
  const setTp = (patch: Partial<Layout['title_page']>) =>
    update((x) => ({ ...x, title_page: { ...x.title_page, ...patch } }))
  const setSec = (patch: Partial<Layout['sections']>) =>
    update((x) => ({ ...x, sections: { ...x.sections, ...patch } }))
  return (
    <div className="space-y-6">
      <Section title="Title page">
        <Field label="Subtitle">
          {(id) => (
            <TextInput
              id={id}
              value={tp.subtitle}
              maxLength={200}
              onCommit={(v) => setTp({ subtitle: v })}
            />
          )}
        </Field>
        <Field label="Author line" hint="For example: by A. Writer">
          {(id) => (
            <TextInput
              id={id}
              value={tp.byline}
              maxLength={200}
              onCommit={(v) => setTp({ byline: v })}
            />
          )}
        </Field>
        <div className="flex flex-wrap gap-4">
          <Checkbox
            checked={tp.show_series}
            onCheckedChange={(v) => setTp({ show_series: v })}
            label="Series title"
          />
          <Checkbox
            checked={tp.show_edition}
            onCheckedChange={(v) => setTp({ show_edition: v })}
            label="Edition"
          />
        </div>
        <div className="w-40">
          <Mm
            max={300}
            label="Space above the title"
            value={tp.top_mm}
            onCommit={(v) => setTp({ top_mm: v })}
          />
        </div>
      </Section>
      <Section title="Sections">
        <div className="grid grid-cols-2 gap-3">
          <Mm
            max={60}
            label="Space between"
            value={sec.gap_mm}
            onCommit={(v) => setSec({ gap_mm: v })}
          />
          <Field label="Divider">
            {(id) => (
              <Select
                id={id}
                value={sec.divider}
                options={[
                  { value: 'none', label: 'None' },
                  { value: 'rule', label: 'Short rule' },
                  { value: 'asterism', label: '* * *' },
                  { value: 'fleuron', label: '❧ Fleuron' },
                ]}
                onValueChange={(v) => v && setSec({ divider: v })}
              />
            )}
          </Field>
          <Field label="Acts start on">
            {(id) => (
              <Select
                id={id}
                value={sec.act_break}
                options={[
                  { value: 'right', label: 'A new right-hand page' },
                  { value: 'page', label: 'A new page' },
                  { value: 'none', label: 'The same page' },
                ]}
                onValueChange={(v) => v && setSec({ act_break: v })}
              />
            )}
          </Field>
        </div>
        <div className="flex flex-col gap-2">
          <Checkbox
            checked={sec.keep_together}
            onCheckedChange={(v) => setSec({ keep_together: v })}
            label="Keep each section on one page where it fits"
          />
          <Checkbox
            checked={sec.hyphenate}
            onCheckedChange={(v) => setSec({ hyphenate: v })}
            label="Hyphenate body text"
          />
        </div>
      </Section>
    </div>
  )
}

// ── signatures & folding ─────────────────────────────────────────────────

function PrintingTab({ l, update }: { l: Layout; update: Update }) {
  const imp = l.imposition
  const set = (patch: Partial<Layout['imposition']>) =>
    update((x) => {
      const imposition = { ...x.imposition, ...patch }
      // Mirror the server: folding fixes the page at half the sheet.
      const page = imposition.fold
        ? foldedPage(imposition.sheet_width_mm, imposition.sheet_height_mm)
        : null
      return {
        ...x,
        imposition,
        ...(page ? { trim_width_mm: page.w, trim_height_mm: page.h } : {}),
      }
    })
  const sheetSize = matchSize(imp.sheet_width_mm, imp.sheet_height_mm)
  const page = foldedPage(imp.sheet_width_mm, imp.sheet_height_mm)
  return (
    <div className="space-y-6">
      <Section
        title="Folded sheets"
        hint="Print two pages on each side of a sheet, then fold it in half. The page becomes half the sheet, and the PDF comes out as sheets in booklet order."
      >
        <Checkbox
          checked={imp.fold}
          onCheckedChange={(v) => set({ fold: v })}
          label="Each sheet holds 2 pages per side (folded)"
        />
        {imp.fold && (
          <>
            <Field label="Sheet size">
              {(id) => (
                <Select
                  id={id}
                  value={sheetSize ?? 'custom'}
                  options={[
                    ...PAGE_SIZES.filter((s) => s.group === 'Paper').map((s) => ({
                      value: s.key,
                      label: `${s.label} → ${foldedPage(s.w, s.h).w} × ${foldedPage(s.w, s.h).h} mm pages`,
                    })),
                    { value: 'custom', label: 'Custom' },
                  ]}
                  onValueChange={(k) => {
                    const s = PAGE_SIZES.find((p) => p.key === k)
                    if (s) set({ sheet_width_mm: s.h, sheet_height_mm: s.w })
                  }}
                />
              )}
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Mm
                min={100}
                max={1200}
                label="Sheet width"
                value={imp.sheet_width_mm}
                onCommit={(v) => set({ sheet_width_mm: v })}
              />
              <Mm
                min={100}
                max={1200}
                label="Sheet height"
                value={imp.sheet_height_mm}
                onCommit={(v) => set({ sheet_height_mm: v })}
              />
            </div>
            <p className="text-sm">
              Pages:{' '}
              <strong className="tabular-nums">
                {page.w} × {page.h} mm
              </strong>
            </p>
          </>
        )}
      </Section>
      <Section
        title="Signatures"
        hint={
          imp.fold
            ? 'Sheets are folded and nested in groups (signatures), then the signatures are stacked and bound. Blank pages fill the last one, before the back cover.'
            : 'For a printer who folds signatures: the page count is padded with blank pages to a whole number of them.'
        }
      >
        <Field label="Pages per signature">
          {(id) => (
            <Select
              id={id}
              value={String(imp.signature_pages)}
              options={[
                ...(SIGNATURES.includes(imp.signature_pages) ? [] : [imp.signature_pages]),
                ...SIGNATURES,
              ].map((n) => ({
                value: String(n),
                label:
                  n === 0
                    ? imp.fold
                      ? 'One signature (saddle stitch)'
                      : 'None (no padding)'
                    : imp.fold && n
                      ? `${n} pages (${n / 4} sheet${n === 4 ? '' : 's'})`
                      : `${n} pages`,
              }))}
              onValueChange={(v) => v !== null && set({ signature_pages: Number(v) })}
            />
          )}
        </Field>
        {imp.fold && (
          <div className="grid grid-cols-2 items-end gap-3">
            <Mm
              max={5}
              label="Creep"
              step={0.05}
              value={imp.creep_mm}
              hint="Shift inner sheets toward the fold by up to this"
              onCommit={(v) => set({ creep_mm: v })}
            />
            <Checkbox
              checked={imp.fold_marks}
              onCheckedChange={(v) => set({ fold_marks: v })}
              label="Fold marks"
            />
          </div>
        )}
      </Section>
      {imp.fold && (
        <p className="rounded-lg bg-surface-2 p-3 text-xs text-muted">
          To print: double-sided, <strong>flip on the short edge</strong>, at actual size. Fold each
          sheet, nest each signature's sheets in order, and stack the signatures. The Export page
          can also build the pages alone, in reading order.
        </p>
      )}
    </div>
  )
}
