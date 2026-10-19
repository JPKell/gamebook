import { useQueryClient } from '@tanstack/react-query'
import { BookOpen, Library, PenLine, ScanSearch, Settings2, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useParams, useSearchParams } from 'react-router'

import { useBook, useBookGraph } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { buttonVariants } from '@/components/ui/button-variants'
import { Dialog } from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty'
import { Field } from '@/components/ui/field'
import { NumberInput, Select } from '@/components/ui/inputs'
import { useCheckConsistency } from '@/features/assist/api'
import { isActive, useJobStream } from '@/features/playtest/api'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'

import { type ProseStatus, STATUS_LABELS, STATUS_TONE, useGenerateAct, useQueue } from './api'
import { PipelineSettings } from './PipelineSettings'
import { Review } from './Review'

export function WritingIndex() {
  const lastBookId = useUiStore((s) => s.lastBookId)
  if (lastBookId) return <Navigate to={`/writing/${lastBookId}`} replace />
  return (
    <EmptyState
      icon={Library}
      title="Open a book to write it"
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

export function WritingPage() {
  const { bookId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const book = useBook(bookId)
  const queue = useQueue(bookId)
  const [filter, setFilter] = useState<ProseStatus | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [actOpen, setActOpen] = useState(false)
  const variantId = params.get('variant') ?? queue.data?.rows[0]?.variant_id ?? null
  const selected = queue.data?.rows.find((r) => r.variant_id === variantId)

  if (book.isError) return <EmptyState icon={BookOpen} title="Book not found" />
  const rows = (queue.data?.rows ?? []).filter((r) => !filter || r.status === filter)
  const byAct = new Map<string, typeof rows>() // by act id: titles can repeat
  for (const r of rows) byAct.set(r.act_id, [...(byAct.get(r.act_id) ?? []), r])

  return (
    <div className="mx-auto flex h-full max-w-[1500px] flex-col gap-4 px-6 py-5">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Writing</h1>
        <span className="text-muted">{book.data?.title}</span>
        <div className="ml-auto flex gap-2">
          <CheckBook bookId={bookId} />
          <Button size="sm" variant="outline" onClick={() => setActOpen(true)}>
            <Sparkles className="size-4" /> Write an act
          </Button>
          <Button size="sm" variant="outline" onClick={() => setSettingsOpen(true)}>
            <Settings2 className="size-4" /> Pipeline settings
          </Button>
        </div>
      </header>
      <div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(0,1fr)] gap-4">
        <aside
          aria-label="Writing queue"
          className="flex min-h-0 flex-col rounded-xl border border-border bg-surface"
        >
          <div className="flex flex-wrap gap-1 border-b border-border p-2">
            {(Object.keys(STATUS_LABELS) as ProseStatus[]).map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={filter === s}
                onClick={() => setFilter(filter === s ? null : s)}
                className={cn(
                  'rounded-full px-2 py-0.5 text-xs',
                  STATUS_TONE[s],
                  filter === s && 'ring-2 ring-accent',
                )}
              >
                {STATUS_LABELS[s]} {queue.data?.counts[s] ?? 0}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-2">
            {[...byAct.entries()].map(([act, items]) => (
              <div key={act} className="mb-2">
                <div className="px-2 pb-1 text-xs font-medium tracking-wide text-muted uppercase">
                  {items[0]?.act_title}
                </div>
                <ul>
                  {items.map((r) => (
                    <li key={r.variant_id}>
                      <button
                        type="button"
                        aria-current={r.variant_id === variantId ? 'true' : undefined}
                        onClick={() => setParams({ variant: r.variant_id }, { replace: true })}
                        className={cn(
                          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm',
                          r.variant_id === variantId ? 'bg-accent/12' : 'hover:bg-surface-2',
                          !r.reachable && 'opacity-60',
                        )}
                      >
                        <span className="min-w-0 flex-1 truncate">
                          {r.node_title}
                          {r.variant_label !== 'Default' && (
                            <span className="text-muted"> · {r.variant_label}</span>
                          )}
                        </span>
                        <span
                          className={cn(
                            'shrink-0 rounded-full px-1.5 text-[11px]',
                            STATUS_TONE[r.status],
                          )}
                        >
                          {STATUS_LABELS[r.status]}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {queue.data && rows.length === 0 && (
              <p className="p-2 text-sm text-muted">Nothing here.</p>
            )}
          </div>
        </aside>
        <section className="min-h-0 overflow-auto">
          {selected ? (
            <Review key={selected.variant_id} bookId={bookId} row={selected} />
          ) : (
            <EmptyState icon={PenLine} title="Pick a section">
              Sections are listed in canonical order: the order most readers meet them.
            </EmptyState>
          )}
        </section>
      </div>
      {book.data && (
        <PipelineSettings
          seriesId={book.data.series_id}
          open={settingsOpen}
          onOpenChange={setSettingsOpen}
        />
      )}
      <ActDialog bookId={bookId} open={actOpen} onOpenChange={setActOpen} />
    </div>
  )
}

function ActDialog({
  bookId,
  open,
  onOpenChange,
}: {
  bookId: string
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const graph = useBookGraph(bookId)
  const generate = useGenerateAct(bookId)
  const qc = useQueryClient()
  const acts = graph.data?.acts ?? []
  const [actId, setActId] = useState<string | null>(null)
  const [only, setOnly] = useState<'missing' | 'stale' | 'all'>('missing')
  const [budget, setBudget] = useState<number | null>(null)
  const job = useJobStream(generate.data?.id, () => {
    void qc.invalidateQueries({ queryKey: ['writing'] })
    void qc.invalidateQueries({ queryKey: ['book', bookId] })
  })
  const act = actId ?? acts[0]?.id ?? null
  const result = job?.result as
    | { written: number; failed: unknown[]; cost_usd: number; stopped: string | null }
    | null
    | undefined
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Write an act"
      description="Runs writer → critic → editor for each section in canonical order, so every section can build on the one before it. Results land in review."
      footer={
        <Button
          disabled={!act || generate.isPending || isActive(job?.status)}
          onClick={() => act && generate.mutate({ actId: act, only, max_cost_usd: budget })}
        >
          <Sparkles className="size-4" /> Start
        </Button>
      }
    >
      <div className="space-y-3">
        <Field label="Act">
          {(id) => (
            <Select
              id={id}
              value={act}
              options={acts.map((a) => ({ value: a.id, label: a.title }))}
              onValueChange={setActId}
            />
          )}
        </Field>
        <Field label="Which sections">
          {(id) => (
            <Select
              id={id}
              value={only}
              options={[
                { value: 'missing', label: 'Not yet written (or only drafts)' },
                { value: 'stale', label: 'Stale approved text' },
                { value: 'all', label: 'Everything' },
              ]}
              onValueChange={(v) => v && setOnly(v)}
            />
          )}
        </Field>
        <Field
          label="Budget (USD)"
          hint="Stops before the next section once spending reaches this. Empty: no cap."
        >
          {(id) => (
            <NumberInput
              id={id}
              min={0}
              step="0.1"
              allowEmpty
              value={budget}
              onCommit={setBudget}
            />
          )}
        </Field>
        {job && (
          <div role="status" className="space-y-1 text-sm">
            {isActive(job.status) ? (
              <p>
                Writing… {job.progress} of {job.total} sections
              </p>
            ) : job.status === 'done' && result ? (
              <p>
                Wrote {result.written} section{result.written === 1 ? '' : 's'} for $
                {result.cost_usd.toFixed(4)}.
                {result.failed.length > 0 && ` ${result.failed.length} failed (see the call log).`}
                {result.stopped && ` ${result.stopped}.`}
              </p>
            ) : (
              <p className="text-danger">{job.error ?? job.status}</p>
            )}
          </div>
        )}
      </div>
    </Dialog>
  )
}

function CheckBook({ bookId }: { bookId: string }) {
  const qc = useQueryClient()
  const check = useCheckConsistency(bookId)
  const job = useJobStream(
    check.data?.id,
    () => void qc.invalidateQueries({ queryKey: ['book', bookId] }),
  )
  const running = check.isPending || isActive(job?.status)
  const result = job?.result as
    | { issues: number; checked: number; failed?: { node_id: string; error: string }[] }
    | null
    | undefined
  const failed = result?.failed?.length ?? 0
  return (
    <div className="flex items-center gap-2">
      {job && !running && (
        <span role="status" className="text-xs text-muted">
          {job.status === 'done' && result
            ? `${result.checked} checked, ${result.issues} issue${result.issues === 1 ? '' : 's'} (see Problems)` +
              (failed ? `; ${failed} couldn't be checked: ${result.failed![0]!.error}` : '')
            : job.error}
        </span>
      )}
      <Button size="sm" variant="outline" disabled={running} onClick={() => check.mutate({})}>
        <ScanSearch className="size-4" />{' '}
        {running ? `Checking ${job?.progress ?? 0}/${job?.total ?? '…'}` : 'Check consistency'}
      </Button>
    </div>
  )
}
