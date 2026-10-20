import { useQueryClient } from '@tanstack/react-query'
import {
  BadgeCheck,
  CircleAlert,
  Download,
  FileText,
  Globe,
  Info,
  LayoutTemplate,
  Library,
  Shuffle,
  TabletSmartphone,
} from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useParams } from 'react-router'

import { useBook } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { buttonVariants } from '@/components/ui/button-variants'
import { EmptyState } from '@/components/ui/empty'
import { Checkbox, NumberInput, Select } from '@/components/ui/inputs'
import { usePageSetup } from '@/features/art/api'
import { Panel } from '@/features/entities/EntityHeader'
import { useSeriesVocab } from '@/features/entities/useSeriesVocab'
import { isActive, useJobStream } from '@/features/playtest/api'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'

import {
  downloadUrl,
  previewUrl,
  usePreflight,
  useReshuffle,
  useStartExport,
  useVerify,
} from './api'

/** /export → the last book opened. */
export function ExportIndex() {
  const lastBookId = useUiStore((s) => s.lastBookId)
  if (lastBookId) return <Navigate to={`/export/${lastBookId}`} replace />
  return (
    <EmptyState
      icon={Library}
      title="Open a book to export it"
      action={
        <Link to="/library" className={buttonVariants()}>
          Go to the Library
        </Link>
      }
    >
      Pick a book in the Library first.
    </EmptyState>
  )
}

/** Print editions: pre-flight, numbering, verification, PDF/EPUB and the proof. */
export function ExportPage() {
  const { bookId = '' } = useParams()
  const book = useBook(bookId)
  const vocab = useSeriesVocab(book.data?.series_id ?? '')
  const [tier, setTier] = useState<string | null>(null)
  const pre = usePreflight(bookId, tier)
  const edition = tier ?? pre.data?.tier ?? null
  const [jump, setJump] = useState<number | null>(null)
  const [reloads, setReloads] = useState(0)
  const base = previewUrl(bookId, edition)
  // Jumping only changes the fragment (no reload); edits need an explicit reload.
  const src = `${base}${jump ? `#s${jump}` : ''}`
  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col gap-4 px-6 py-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Export</h1>
        <span className="text-muted">{book.data?.title}</span>
        <Link
          to={`/export/${bookId}/layout`}
          className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), 'ml-auto')}
        >
          <LayoutTemplate className="size-4" /> Page layout
        </Link>
        <Select
          aria-label="Edition"
          value={edition}
          options={vocab.tiers.map((t) => ({ value: t.key, label: `${t.label} edition` }))}
          onValueChange={(t) => t && setTier(t)}
          className="w-auto"
        />
      </header>
      {pre.error && (
        <p role="alert" className="text-sm text-danger">
          {pre.error.message}
        </p>
      )}
      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[380px_minmax(0,1fr)]">
        <div className="min-h-0 space-y-4 overflow-auto pb-6">
          <Downloads bookId={bookId} tier={edition} seriesId={book.data?.series_id} />
          <Preflight bookId={bookId} tier={edition} onJump={setJump} />
          <Verify bookId={bookId} tier={edition} />
          <Numbering bookId={bookId} tier={edition} />
        </div>
        <section
          aria-label="Proof"
          className="flex min-h-[70vh] flex-col overflow-hidden rounded-xl border border-border"
        >
          <div className="flex items-center gap-2 border-b border-border bg-surface px-3 py-2 text-sm">
            <span className="font-medium">Proof</span>
            <span className="text-xs text-muted">Click a section number to follow it.</span>
            <label className="ml-auto flex items-center gap-1 text-xs text-muted">
              Go to section
              <NumberInput
                aria-label="Go to section"
                min={1}
                allowEmpty
                value={jump}
                onCommit={setJump}
                className="w-20"
              />
            </label>
            <Button size="sm" variant="ghost" onClick={() => setReloads((r) => r + 1)}>
              Reload
            </Button>
          </div>
          {edition && (
            <iframe
              key={`${base}:${pre.data?.seed ?? ''}:${reloads}`}
              title="Print proof"
              src={src}
              sandbox=""
              className="min-h-0 w-full flex-1 bg-white"
            />
          )}
        </section>
      </div>
    </div>
  )
}

function Downloads({
  bookId,
  tier,
  seriesId,
}: {
  bookId: string
  tier: string | null
  seriesId: string | undefined
}) {
  const setup = usePageSetup(bookId)
  const folded = !!setup.data?.imposition?.fold
  const padded = !!setup.data?.imposition?.signature_pages
  const imposes = folded || padded
  const [sheets, setSheets] = useState(true)
  return (
    <Panel title="Download">
      <div className="grid gap-2">
        {imposes && (
          <Checkbox
            checked={sheets}
            onCheckedChange={setSheets}
            label={
              folded
                ? 'PDF on folded sheets (off: pages in reading order)'
                : 'Pad to whole signatures (off: pages as they are)'
            }
          />
        )}
        {/* Keyed by edition: a finished build belongs to the tier it was built for. */}
        <ExportButton
          key={`pdf:${tier}:${imposes && sheets}`}
          bookId={bookId}
          tier={tier}
          format="pdf"
          imposed={!imposes || sheets}
        />
        <ExportButton key={`epub:${tier}`} bookId={bookId} tier={tier} format="epub" />
        <ExportButton key="web" bookId={bookId} tier={tier} format="web" />
        <p className="text-xs text-muted">
          The web player is a folder of files: unzip it and open <code>index.html</code>, or put it
          on any web host to install it as an app that plays offline. Every edition is included;
          saves stay on the reader's device.
        </p>
        {seriesId && (
          <a
            href={`/api/series/${seriesId}/export.zip`}
            download
            className={buttonVariants({ variant: 'outline', size: 'sm' })}
          >
            <Download className="size-4" /> Series as a git-friendly zip
          </a>
        )}
      </div>
    </Panel>
  )
}

function ExportButton({
  bookId,
  tier,
  format,
  imposed = true,
}: {
  bookId: string
  tier: string | null
  format: 'pdf' | 'epub' | 'web'
  imposed?: boolean
}) {
  const start = useStartExport(bookId)
  const job = useJobStream(start.data?.id)
  const running = start.isPending || isActive(job?.status)
  const result =
    job?.status === 'done'
      ? (job.result as {
          file: string
          pages?: number
          blanks?: number
          sheets?: number
          signatures?: number
          bytes: number
          warnings?: { message: string }[]
        })
      : null
  const Icon = format === 'pdf' ? FileText : format === 'web' ? Globe : TabletSmartphone
  const what = format === 'web' ? 'web player' : format.toUpperCase()
  return (
    <div className="space-y-1 rounded-lg border border-border p-2">
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={running || (!tier && format !== 'web')}
          onClick={() => start.mutate({ tier, format, imposed })}
        >
          <Icon className="size-4" /> {running ? 'Building…' : `Build ${what}`}
        </Button>
        {result && start.data && (
          <a href={downloadUrl(start.data.id)} className="text-sm text-accent hover:underline">
            Download {result.file}
          </a>
        )}
      </div>
      {result && (
        <p className="text-xs text-muted">
          {result.pages ? `${result.pages} pages · ` : ''}
          {result.blanks ? `${result.blanks} blank to fill the signatures · ` : ''}
          {result.sheets
            ? `${result.sheets} sheets in ${result.signatures} signature${result.signatures === 1 ? '' : 's'} · `
            : ''}
          {Math.round(result.bytes / 1024)} KB
        </p>
      )}
      {result?.warnings?.length ? (
        <ul aria-label={`${format} layout warnings`} className="space-y-0.5 text-xs text-warning">
          {result.warnings.map((w, i) => (
            <li key={i}>{w.message}</li>
          ))}
        </ul>
      ) : null}
      {(start.error || job?.status === 'failed') && (
        <p className="text-xs text-danger">{start.error?.message ?? job?.error}</p>
      )}
    </div>
  )
}

function Preflight({
  bookId,
  tier,
  onJump,
}: {
  bookId: string
  tier: string | null
  onJump: (n: number) => void
}) {
  const pre = usePreflight(bookId, tier)
  const d = pre.data
  if (!d)
    return (
      <Panel title="Pre-flight">
        {pre.isPending ? <p className="text-sm text-muted">Checking…</p> : null}
      </Panel>
    )
  const severe = d.art.filter((p) => p.severity !== 'info')
  return (
    <Panel title="Pre-flight">
      <dl className="grid grid-cols-2 gap-2 text-sm">
        {(
          [
            ['Sections', d.sections],
            ['Router sections', d.routers],
            ['Tick boxes', d.tick_boxes],
            ['Without prose', d.drafts],
          ] as const
        ).map(([label, value]) => (
          <div key={label} className="rounded-lg bg-surface-2 px-2 py-1">
            <dt className="text-xs text-muted">{label}</dt>
            <dd
              className={cn(
                'font-semibold tabular-nums',
                label === 'Without prose' && value > 0 && 'text-warning',
              )}
            >
              {value}
            </dd>
          </div>
        ))}
      </dl>
      <ProblemList
        title="Print"
        rows={d.warnings.map((w) => ({
          ...w,
          severity: w.code === 'no_prose' ? 'info' : 'warning',
        }))}
        bookId={bookId}
        onJump={onJump}
      />
      <ProblemList
        title={`Artwork${severe.length ? ` (${severe.length} to fix)` : ''}`}
        rows={d.art.map((p) => ({ ...p, number: null }))}
        bookId={bookId}
        onJump={onJump}
      />
    </Panel>
  )
}

function ProblemList({
  title,
  rows,
  bookId,
  onJump,
}: {
  title: string
  rows: {
    code: string
    message: string
    severity: string
    node_id?: string | null
    number?: number | null
  }[]
  bookId: string
  onJump: (n: number) => void
}) {
  const [all, setAll] = useState(false)
  const shown = all ? rows : rows.slice(0, 8)
  return (
    <div className="space-y-1">
      <h3 className="text-xs font-semibold text-muted">{title}</h3>
      {rows.length === 0 ? (
        <p className="flex items-center gap-1 text-sm text-success">
          <BadgeCheck className="size-4" aria-hidden /> Nothing to fix.
        </p>
      ) : (
        <ul className="space-y-1 text-sm">
          {shown.map((r, i) => (
            <li key={i} className="flex items-start gap-1.5">
              {r.severity === 'info' ? (
                <Info className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden />
              ) : (
                <CircleAlert
                  className={cn(
                    'mt-0.5 size-3.5 shrink-0',
                    r.severity === 'error' ? 'text-danger' : 'text-warning',
                  )}
                  aria-hidden
                />
              )}
              <span className="min-w-0">
                {r.message}
                {r.number != null && (
                  <button
                    type="button"
                    onClick={() => onJump(r.number!)}
                    className="ml-1 text-accent hover:underline"
                  >
                    §{r.number}
                  </button>
                )}
                {r.node_id && (
                  <Link
                    to={`/story/${bookId}?node=${r.node_id}`}
                    className="ml-1 text-xs text-accent hover:underline"
                  >
                    open
                  </Link>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {rows.length > 8 && (
        <button
          type="button"
          onClick={() => setAll((a) => !a)}
          className="text-xs text-accent hover:underline"
        >
          {all ? 'Show fewer' : `Show all ${rows.length}`}
        </button>
      )}
    </div>
  )
}

function Verify({ bookId, tier }: { bookId: string; tier: string | null }) {
  const verify = useVerify(bookId)
  const [runs, setRuns] = useState(200)
  const r = verify.data
  return (
    <Panel title="Verify the printed book">
      <p className="text-xs text-muted">
        Bots play the book in the engine; every move must have its printed instruction and the right
        section number.
      </p>
      <div className="flex items-center gap-2">
        <NumberInput
          aria-label="Games to play"
          min={1}
          max={500}
          value={runs}
          onCommit={(v) => v && setRuns(Math.min(500, v))}
          className="w-24"
        />
        <Button
          size="sm"
          disabled={verify.isPending || !tier}
          onClick={() => verify.mutate({ tier, runs })}
        >
          {verify.isPending ? 'Playing…' : 'Verify'}
        </Button>
      </div>
      {verify.error && <p className="text-xs text-danger">{verify.error.message}</p>}
      {r && (
        <div role="status" className="space-y-1 text-sm">
          <p className={r.ok ? 'text-success' : 'text-danger'}>
            {r.ok
              ? `Verified: ${r.runs} games, ${r.moves} moves, all printed correctly.`
              : `${r.problems + r.structure.length} problem(s) in ${r.runs} games.`}
          </p>
          {[...r.structure, ...r.samples].map((s) => (
            <p key={s} className="text-xs text-danger">
              {s}
            </p>
          ))}
          {r.unvisited.length > 0 && (
            <p className="text-xs text-muted">
              Not reached by these games: {r.unvisited.slice(0, 30).join(', ')}
              {r.unvisited.length > 30 ? '…' : ''}
            </p>
          )}
        </div>
      )}
    </Panel>
  )
}

function Numbering({ bookId, tier }: { bookId: string; tier: string | null }) {
  const qc = useQueryClient()
  const pre = usePreflight(bookId, tier)
  const shuffle = useReshuffle(bookId)
  return (
    <Panel title="Section numbers">
      <p className="text-xs text-muted">
        Sections are shuffled within each act (act 1 first) and keep their numbers between exports.
        Pin a number in a section's inspector; the start is section 1.
      </p>
      <p className="text-sm">
        Seed: <span className="font-mono">{pre.data?.seed ?? '…'}</span>
      </p>
      <Button
        size="sm"
        variant="outline"
        disabled={shuffle.isPending}
        onClick={() => {
          if (
            !window.confirm(
              'Renumber every unpinned section? Printed copies and notes using the old numbers will no longer match.',
            )
          )
            return
          shuffle.mutate(null, {
            onSuccess: () => void qc.invalidateQueries({ queryKey: ['book', bookId, 'print'] }),
          })
        }}
      >
        <Shuffle className="size-4" /> Reshuffle numbers
      </Button>
      {shuffle.error && <p className="text-xs text-danger">{shuffle.error.message}</p>}
    </Panel>
  )
}
