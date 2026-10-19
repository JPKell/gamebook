import { useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown, ChevronRight, GitCompare, Sparkles, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { Select, TextArea } from '@/components/ui/inputs'
import { isActive, useJobStream } from '@/features/playtest/api'
import { cn } from '@/lib/utils'

import {
  type ProseOut,
  type QueueRow,
  STATUS_LABELS,
  STATUS_TONE,
  useApprove,
  useContext,
  useGenerate,
  useNodeProse,
  usePipelineRun,
  useReject,
  useSaveSummary,
  useWriteProse,
} from './api'
import { diffWords } from './diff'
import { Findings } from './Findings'

const words = (t: string) => (t.trim() ? t.trim().split(/\s+/).length : 0)

export function Review({ bookId, row }: { bookId: string; row: QueueRow }) {
  const prose = useNodeProse(bookId, row.node_id)
  const variant = prose.data?.variants.find((v) => v.variant_id === row.variant_id)
  const versions = variant?.versions ?? []
  // A picked version only sticks until a newer version arrives.
  const [pick, setPick] = useState<{ latest: string | undefined; id: string } | null>(null)
  const versionId = pick && pick.latest === variant?.latest?.id ? pick.id : null
  const setVersionId = (id: string | null) =>
    setPick(id ? { latest: variant?.latest?.id, id } : null)
  const current = versions.find((v) => v.id === versionId) ?? variant?.latest ?? null

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-semibold">{row.node_title}</h2>
        {row.variant_label !== 'Default' && (
          <span className="text-muted">· {row.variant_label}</span>
        )}
        <span className={cn('rounded-full px-2 py-0.5 text-xs', STATUS_TONE[row.status])}>
          {STATUS_LABELS[row.status]}
        </span>
        <Link
          to={`/story/${bookId}?node=${row.node_id}`}
          className="ml-auto text-sm text-accent hover:underline"
        >
          Open in story
        </Link>
      </header>
      {row.status === 'stale' && (
        <p role="status" className="rounded-lg border border-warning/40 bg-warning/8 p-3 text-sm">
          The approved text was written for different beat notes, lore or a different previous
          section. Regenerate, or re-approve it if it still fits.
        </p>
      )}
      <Generate bookId={bookId} variantId={row.variant_id} hasText={versions.length > 0} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,320px)_minmax(0,1fr)_minmax(0,320px)]">
        <ContextPanel bookId={bookId} variantId={row.variant_id} />
        <div className="space-y-3">
          {versions.length > 1 && (
            <Select
              aria-label="Version"
              value={current?.id ?? null}
              options={versions.map((v, i) => ({
                value: v.id,
                label: `${i === 0 ? 'Latest' : `v${versions.length - i}`} · ${v.status.replace('_', ' ')} · ${v.source} · ${new Date(v.created_at).toLocaleString()}`,
              }))}
              onValueChange={setVersionId}
            />
          )}
          {current ? (
            <Draft
              key={current.id}
              bookId={bookId}
              version={current}
              versions={versions}
              stale={row.status === 'stale'}
            />
          ) : (
            <HandWrite bookId={bookId} variantId={row.variant_id} />
          )}
        </div>
        <div className="space-y-4">
          <Critique runId={current?.pipeline_run_id ?? null} />
          <Findings
            bookId={bookId}
            nodeId={row.node_id}
            variantId={row.variant_id}
            hasProse={versions.length > 0}
          />
        </div>
      </div>
    </div>
  )
}

function Generate({
  bookId,
  variantId,
  hasText,
}: {
  bookId: string
  variantId: string
  hasText: boolean
}) {
  const qc = useQueryClient()
  const generate = useGenerate(bookId)
  const [notes, setNotes] = useState('')
  const job = useJobStream(generate.data?.id, () => {
    void qc.invalidateQueries({ queryKey: ['writing'] })
    void qc.invalidateQueries({ queryKey: ['book', bookId] })
  })
  const running = generate.isPending || isActive(job?.status)
  return (
    <section
      aria-label="Generate"
      className="flex flex-wrap items-start gap-2 rounded-xl border border-border bg-surface p-3"
    >
      <textarea
        aria-label="Notes for the writer"
        rows={1}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder={
          hasText
            ? 'Notes for the rewrite, e.g. “more dread, shorter”'
            : 'Optional notes for the writer'
        }
        className="min-h-8 min-w-64 flex-1 resize-y rounded-md border border-border bg-bg px-2.5 py-1.5 text-sm focus:border-accent focus:outline-none"
      />
      <Button disabled={running} onClick={() => generate.mutate({ variantId, notes })}>
        <Sparkles className="size-4" /> {running ? 'Writing…' : hasText ? 'Regenerate' : 'Generate'}
      </Button>
      {job && !isActive(job.status) && job.status !== 'done' && (
        <p role="alert" className="w-full text-sm text-danger">
          {job.error ?? `Generation ${job.status}`}
        </p>
      )}
    </section>
  )
}

function ContextPanel({ bookId, variantId }: { bookId: string; variantId: string }) {
  const ctx = useContext(bookId, variantId)
  const [open, setOpen] = useState<Record<string, boolean>>({
    node: true,
    choices: true,
    digest: true,
  })
  const c = ctx.data
  if (!c) return <p className="text-sm text-muted">Loading context…</p>
  const x = c.ctx as Record<string, any>
  const sections: { key: string; label: string; body: React.ReactNode; show: boolean }[] = [
    {
      key: 'node',
      label: 'Beat notes',
      show: true,
      body: <p className="whitespace-pre-wrap">{x.node?.beat_notes || '(none)'}</p>,
    },
    {
      key: 'choices',
      label: 'Choices to set up',
      show: true,
      body: x.choices?.length ? (
        <ul className="list-disc pl-5">
          {x.choices.map((t: string) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      ) : (
        <p>(an ending, or no choices yet)</p>
      ),
    },
    {
      key: 'digest',
      label: 'What readers have',
      show: true,
      body: (
        <>
          <p>
            <span className="text-muted">Every reader:</span>{' '}
            {x.digest?.must_text || 'nothing in particular'}
          </p>
          <p>
            <span className="text-muted">Only some:</span> {x.digest?.may_text || 'nothing'}
          </p>
        </>
      ),
    },
    {
      key: 'previous_text',
      label: `Previous section${x.previous_title ? `: ${x.previous_title}` : ''}`,
      show: !!x.previous_text,
      body: <p className="whitespace-pre-wrap">{x.previous_text}</p>,
    },
    {
      key: 'story_so_far',
      label: 'Story so far',
      show: !!x.story_so_far?.length,
      body: (
        <ol className="list-decimal pl-5">
          {(x.story_so_far ?? []).map((s: string, i: number) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      ),
    },
    {
      key: 'beats',
      label: 'Act & beats',
      show: !!(x.act?.summary || x.beats?.length),
      body: (
        <>
          {x.act?.summary && <p>{x.act.summary}</p>}
          <ul className="list-disc pl-5">
            {(x.beats ?? []).map((b: any) => (
              <li key={b.title}>
                {b.title}
                {b.description && ` — ${b.description}`}
              </li>
            ))}
          </ul>
        </>
      ),
    },
    {
      key: 'characters',
      label: 'Characters & place',
      show: !!(x.characters?.length || x.location),
      body: (
        <>
          {x.location && (
            <p>
              <span className="font-medium">{x.location.name}:</span> {x.location.text}
            </p>
          )}
          {(x.characters ?? []).map((ch: any) => (
            <p key={ch.name}>
              <span className="font-medium">{ch.name}</span>
              {ch.role && ` (${ch.role})`}: {ch.lines.join(' ')}
            </p>
          ))}
        </>
      ),
    },
    {
      key: 'style',
      label: 'Style',
      show: true,
      body: (
        <p>
          {x.style?.pov} person, {x.style?.tense} tense, {x.style?.word_min}–{x.style?.word_max}{' '}
          words. {x.style?.voice}
        </p>
      ),
    },
  ]
  const pct = Math.min(100, (c.tokens / c.budget) * 100)
  return (
    <section
      aria-label="Context"
      className="space-y-2 rounded-xl border border-border bg-surface p-3 text-sm"
    >
      <h3 className="font-semibold">What the writer sees</h3>
      <div className="space-y-1">
        <div className="h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
          <div
            className={cn('h-full rounded-full', pct > 90 ? 'bg-warning' : 'bg-accent')}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-xs text-muted tabular-nums">
          ≈ {c.tokens.toLocaleString()} of {c.budget.toLocaleString()} tokens
          {c.trimmed.length > 0 && ` · trimmed: ${c.trimmed.join(', ')}`}
        </p>
      </div>
      {sections
        .filter((s) => s.show)
        .map((s) => (
          <div key={s.key}>
            <button
              type="button"
              aria-expanded={!!open[s.key]}
              onClick={() => setOpen((o) => ({ ...o, [s.key]: !o[s.key] }))}
              className="flex w-full items-center gap-1 py-1 text-left text-xs font-medium tracking-wide text-muted uppercase hover:text-text"
            >
              {open[s.key] ? (
                <ChevronDown className="size-3.5" />
              ) : (
                <ChevronRight className="size-3.5" />
              )}
              {s.label}
            </button>
            {open[s.key] && <div className="space-y-1 pb-2 pl-4">{s.body}</div>}
          </div>
        ))}
    </section>
  )
}

function Draft({
  bookId,
  version: v,
  versions,
  stale,
}: {
  bookId: string
  version: ProseOut
  versions: ProseOut[]
  /** The variant's approved text is stale (re-approving refreshes it). */
  stale: boolean
}) {
  const approve = useApprove(bookId)
  const reject = useReject(bookId)
  const saveSummary = useSaveSummary(bookId)
  const [text, setText] = useState(v.text)
  const [showDiff, setShowDiff] = useState(false)
  const parent = versions.find((x) => x.id === v.parent_id)
  const pieces = useMemo(
    () => (showDiff && parent ? diffWords(parent.text, text) : []),
    [showDiff, parent, text],
  )
  const edited = text.trim() !== v.text.trim()
  const reviewable = v.status === 'in_review' || v.status === 'draft'
  const old = v.status === 'superseded' || v.status === 'rejected'
  const staleApproved = stale && v.status === 'approved'
  const label = edited
    ? 'Approve with my edits'
    : old
      ? 'Restore this version'
      : staleApproved
        ? 'Re-approve: it still fits'
        : v.status === 'approved'
          ? 'Approved'
          : 'Approve'
  return (
    <section
      aria-label="Draft"
      className="space-y-3 rounded-xl border border-border bg-surface p-3"
    >
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <span className="capitalize">{v.status.replace('_', ' ')}</span>
        <span>· {v.source === 'llm' ? 'written by the pipeline' : 'written by you'}</span>
        <span>· {words(text)} words</span>
        {parent && (
          <Button
            size="sm"
            variant="ghost"
            aria-pressed={showDiff}
            className="ml-auto"
            onClick={() => setShowDiff((d) => !d)}
          >
            <GitCompare className="size-4" /> {showDiff ? 'Hide changes' : 'Changes since previous'}
          </Button>
        )}
      </div>
      {showDiff && parent ? (
        <div
          aria-label="Changes"
          className="max-h-[60vh] overflow-auto rounded-md border border-border bg-bg p-3 font-serif text-[15px] leading-relaxed whitespace-pre-wrap"
        >
          {pieces.map((p, i) =>
            p.op === 'eq' ? (
              <span key={i}>{p.text}</span>
            ) : p.op === 'add' ? (
              <ins key={i} className="bg-success/15 text-success no-underline">
                {p.text}
              </ins>
            ) : (
              <del key={i} className="bg-danger/12 text-danger">
                {p.text}
              </del>
            ),
          )}
        </div>
      ) : (
        <textarea
          aria-label="Prose"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={16}
          className="w-full rounded-md border border-border bg-bg p-3 font-serif text-[15px] leading-relaxed focus:border-accent focus:outline-none"
        />
      )}
      {v.notes && <p className="text-xs text-muted">Notes: {v.notes}</p>}
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() => approve.mutate({ id: v.id, text: edited ? text : undefined })}
          disabled={approve.isPending || (v.status === 'approved' && !edited && !staleApproved)}
        >
          <Check className="size-4" /> {label}
        </Button>
        {reviewable && (
          <Button
            variant="outline"
            onClick={() => {
              const notes = window.prompt('Why reject it? (kept with the version)') ?? undefined
              if (notes !== undefined) reject.mutate({ id: v.id, notes })
            }}
          >
            <X className="size-4" /> Reject
          </Button>
        )}
        {edited && (
          <Button variant="ghost" onClick={() => setText(v.text)}>
            Discard edits
          </Button>
        )}
      </div>
      <div className="space-y-1">
        <label className="text-xs font-medium text-muted" htmlFor={`summary-${v.id}`}>
          Summary (used as “story so far” for later sections)
        </label>
        <TextArea
          id={`summary-${v.id}`}
          rows={2}
          value={v.summary}
          onCommit={(summary) => saveSummary.mutate({ id: v.id, summary })}
        />
      </div>
    </section>
  )
}

function HandWrite({ bookId, variantId }: { bookId: string; variantId: string }) {
  const write = useWriteProse(bookId)
  const [text, setText] = useState('')
  return (
    <section
      aria-label="Write by hand"
      className="space-y-2 rounded-xl border border-border bg-surface p-3"
    >
      <p className="text-sm text-muted">No prose yet. Generate it above, or write it yourself:</p>
      <textarea
        aria-label="Prose"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={12}
        className="w-full rounded-md border border-border bg-bg p-3 font-serif text-[15px] leading-relaxed focus:border-accent focus:outline-none"
      />
      <div className="flex gap-2">
        <Button
          disabled={!text.trim()}
          onClick={() => write.mutate({ variantId, text, approve: true })}
        >
          <Check className="size-4" /> Save & approve
        </Button>
        <Button
          variant="outline"
          disabled={!text.trim()}
          onClick={() => write.mutate({ variantId, text, approve: false })}
        >
          Save as draft
        </Button>
      </div>
    </section>
  )
}

const RUBRIC_LABELS: Record<string, string> = {
  beat_adherence: 'Beat',
  continuity: 'Continuity',
  path_validity: 'Path validity',
  style: 'Style',
  choice_setup: 'Choice setup',
  prose_quality: 'Prose',
}

function Critique({ runId }: { runId: string | null }) {
  const run = usePipelineRun(runId)
  if (!runId) return <aside className="text-sm text-muted">Written by hand: no critique.</aside>
  const r = run.data
  if (!r) return <aside className="text-sm text-muted">Loading critique…</aside>
  const critiques = r.trail.filter((t) => t.kind === 'critique')
  return (
    <aside
      aria-label="Critique"
      className="space-y-3 rounded-xl border border-border bg-surface p-3 text-sm"
    >
      <h3 className="font-semibold">Critique trail</h3>
      <p className="text-xs text-muted tabular-nums">
        {critiques.length} critique{critiques.length === 1 ? '' : 's'}, {r.iterations} rewrite
        {r.iterations === 1 ? '' : 's'}
        {r.final_score != null && ` · final score ${r.final_score.toFixed(1)}`} · $
        {r.cost_usd.toFixed(4)}
      </p>
      {r.notes && (
        <p className="text-xs">
          <span className="text-muted">Your notes:</span> {r.notes}
        </p>
      )}
      {critiques.map((c, i) => {
        const report = (c.report ?? {}) as {
          scores?: Record<string, number>
          issues?: { quote?: string; problem: string; suggestion?: string }[]
          summary?: string
        }
        return (
          <div key={i} className="space-y-1.5 border-t border-border pt-2">
            <p className="font-medium">
              Pass {i + 1}: {typeof c.score === 'number' ? c.score.toFixed(1) : '—'} / 10
            </p>
            <dl className="grid grid-cols-2 gap-x-3 text-xs">
              {Object.entries(report.scores ?? {}).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <dt className="text-muted">{RUBRIC_LABELS[k] ?? k}</dt>
                  <dd className="tabular-nums">{v}</dd>
                </div>
              ))}
            </dl>
            {report.summary && <p className="text-xs italic">{report.summary}</p>}
            <ul className="space-y-1">
              {(report.issues ?? []).map((iss, j) => (
                <li key={j} className="text-xs">
                  {iss.quote && <q className="text-muted">{iss.quote}</q>} {iss.problem}
                  {iss.suggestion && <span className="text-muted"> → {iss.suggestion}</span>}
                </li>
              ))}
            </ul>
          </div>
        )
      })}
      {r.error && <p className="text-danger">{r.error}</p>}
      <Link to={`/settings?tab=calls`} className="text-xs text-accent hover:underline">
        See every call in the log
      </Link>
    </aside>
  )
}
