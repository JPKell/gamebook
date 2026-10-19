import { useQueryClient } from '@tanstack/react-query'
import {
  Bot,
  CircleAlert,
  FlaskConical,
  Gamepad2,
  GitCompare,
  Library,
  Map,
  Play,
  Sparkles,
  Square,
  Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useParams, useSearchParams } from 'react-router'

import { useBook, useBookGraph, useRuleSystems } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { buttonVariants } from '@/components/ui/button-variants'
import { EmptyState } from '@/components/ui/empty'
import { Field } from '@/components/ui/field'
import { NumberInput, Select, TextInput } from '@/components/ui/inputs'
import { cn } from '@/lib/utils'
import { useProviders } from '@/features/llm/api'
import { useUiStore } from '@/stores/ui'

import {
  type BatchOut,
  type BotName,
  isActive,
  pk,
  useBatch,
  useBatches,
  useBots,
  useCancelJob,
  useCreateBatch,
  useDeleteBatch,
  useJobStream,
  useResumeBatch,
  useStartCoverage,
} from './api'
import { Compare } from './Compare'
import { Dashboard } from './Dashboard'
import { Player } from './Player'
import { Replay } from './Replay'
import { pct, usd } from './summary'

/** /playtest → the last book opened. */
export function PlaytestIndex() {
  const lastBookId = useUiStore((s) => s.lastBookId)
  if (lastBookId) return <Navigate to={`/playtest/${lastBookId}`} replace />
  return (
    <EmptyState
      icon={Library}
      title="Open a book to playtest it"
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

type View = 'batches' | 'play' | 'coverage'

export function PlaytestPage() {
  const { bookId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const book = useBook(bookId)
  const systems = useRuleSystems(book.data?.series_id)
  const uiTier = useUiStore((s) => s.tier)
  const view: View =
    (['play', 'coverage'] as const).find((v) => v === params.get('view')) ?? 'batches'
  const set = (patch: Record<string, string | null>) =>
    setParams(
      (p) => {
        for (const [k, v] of Object.entries(patch)) {
          if (v === null) p.delete(k)
          else p.set(k, v)
        }
        return p
      },
      { replace: true },
    )

  if (book.isPending || (book.data && systems.isPending))
    return <p className="p-6 text-muted">Loading…</p>
  if (book.isError || !book.data)
    return (
      <EmptyState icon={Library} title="Book not found">
        It may have been deleted.{' '}
        <Link to="/library" className="text-accent underline">
          Back to the Library
        </Link>
      </EmptyState>
    )
  const rules = systems.data?.find((r) => r.is_active)
  const tiers = (rules?.definition.tiers ?? []).map((t) => ({ key: t.key, label: t.label }))
  const defaultTier = tiers.find((t) => t.key === uiTier)?.key ?? tiers[0]?.key ?? ''

  return (
    <div className="mx-auto max-w-7xl space-y-5 px-6 py-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Playtest</h1>
        <span className="text-muted">{book.data.title}</span>
        <div
          role="radiogroup"
          aria-label="Playtest view"
          className="ml-auto flex rounded-md border border-border bg-bg p-0.5"
        >
          {(
            [
              ['batches', 'Bot batches', Bot],
              ['play', 'Play', Gamepad2],
              ['coverage', 'Coverage', Map],
            ] as const
          ).map(([v, label, Icon]) => (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={view === v}
              onClick={() => set({ view: v === 'batches' ? null : v })}
              className={cn(
                'flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium',
                view === v ? 'bg-accent text-accent-fg' : 'text-muted hover:text-text',
              )}
            >
              <Icon className="size-3.5" aria-hidden /> {label}
            </button>
          ))}
        </div>
      </header>
      {!rules ? (
        <EmptyState icon={FlaskConical} title="No active rule system">
          Books are played with their series' active rules. Make one active in Mechanics.
        </EmptyState>
      ) : view === 'play' ? (
        <Player key={bookId} bookId={bookId} tiers={tiers} defaultTier={defaultTier} />
      ) : view === 'coverage' ? (
        <Coverage bookId={bookId} tiers={tiers} defaultTier={defaultTier} />
      ) : (
        <Batches
          bookId={bookId}
          tiers={tiers}
          defaultTier={defaultTier}
          params={params}
          set={set}
        />
      )}
    </div>
  )
}

function Batches({
  bookId,
  tiers,
  defaultTier,
  params,
  set,
}: {
  bookId: string
  tiers: { key: string; label: string }[]
  defaultTier: string
  params: URLSearchParams
  set: (patch: Record<string, string | null>) => void
}) {
  const batches = useBatches(bookId)
  const selectedId =
    params.get('batch') ?? batches.data?.find((b) => b.win_rate != null)?.id ?? null
  const compareId = params.get('compare')
  const run = params.get('run')
  const selected = useBatch(selectedId)
  const del = useDeleteBatch(bookId)

  return (
    <div className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
      <div className="space-y-4">
        <NewBatch
          bookId={bookId}
          tiers={tiers}
          defaultTier={defaultTier}
          onCreated={(id) => set({ batch: id, run: null, compare: null })}
        />
        <section aria-label="Batches" className="rounded-xl border border-border bg-surface">
          <h2 className="border-b border-border px-4 py-2.5 text-sm font-semibold">Batches</h2>
          {batches.data?.length === 0 && <p className="p-4 text-sm text-muted">No batches yet.</p>}
          <ul className="divide-y divide-border">
            {(batches.data ?? []).map((b) => (
              <BatchRow
                key={b.id}
                bookId={bookId}
                batch={b}
                selected={b.id === selectedId}
                comparing={b.id === compareId}
                onSelect={() =>
                  set({ batch: b.id, run: null, compare: compareId === b.id ? null : compareId })
                }
                onCompare={
                  selectedId && b.id !== selectedId && b.win_rate != null && !isActive(b.status)
                    ? () => set({ compare: compareId === b.id ? null : b.id })
                    : undefined
                }
                onDelete={() => {
                  if (!window.confirm(`Delete "${b.label}" and its runs?`)) return
                  del.mutate(b.id)
                  if (b.id === selectedId) set({ batch: null, run: null })
                  if (b.id === compareId) set({ compare: null })
                }}
              />
            ))}
          </ul>
        </section>
      </div>
      <div className="min-w-0 space-y-4">
        {compareId && selected.data && (
          <Compare a={selected.data} bId={compareId} onClose={() => set({ compare: null })} />
        )}
        {run !== null && selected.data && (
          <Replay
            key={`${selected.data.id}:${run}`}
            batch={selected.data}
            index={Number(run)}
            initialStep={params.get('step') === null ? null : Number(params.get('step'))}
            onClose={() => set({ run: null, step: null })}
          />
        )}
        {selected.data?.summary ? (
          <>
            <h2 className="text-lg font-semibold">{selected.data.label}</h2>
            <Dashboard
              batch={selected.data}
              onReplay={(i, step) =>
                set({ run: String(i), step: step === undefined ? null : String(step) })
              }
            />
          </>
        ) : (
          !selectedId && (
            <EmptyState icon={Bot} title="Run some bots">
              Bots play the book thousands of times so you can see who wins, where readers die, and
              what never gets visited.
            </EmptyState>
          )
        )}
      </div>
    </div>
  )
}

function BatchRow({
  bookId,
  batch,
  selected,
  comparing,
  onSelect,
  onCompare,
  onDelete,
}: {
  bookId: string
  batch: BatchOut
  selected: boolean
  comparing: boolean
  onSelect: () => void
  onCompare?: () => void
  onDelete: () => void
}) {
  const qc = useQueryClient()
  const cancel = useCancelJob()
  const resume = useResumeBatch(bookId)
  const active = isActive(batch.status)
  const llm = batch.player.kind === 'llm'
  const resumable = llm && ['stopped', 'cancelled', 'failed'].includes(batch.status)
  const cap = batch.player.budget_usd as number | null | undefined
  const spent = batch.cost_usd ?? 0
  const overBudget = cap != null && spent >= cap
  const [asking, setAsking] = useState(false)
  const [newBudget, setNewBudget] = useState<number | null>(null)
  const budgetOk = newBudget !== null && newBudget > spent
  const job = useJobStream(active ? batch.job_id : null, () => {
    void qc.invalidateQueries({ queryKey: pk.batches(bookId) })
    void qc.invalidateQueries({ queryKey: pk.batch(batch.id) })
  })
  const progress = job && job.total ? job.progress / job.total : 0
  return (
    <li className={cn('px-4 py-2.5', selected && 'bg-accent/8')}>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onSelect}
          aria-current={selected ? 'true' : undefined}
          className="min-w-0 flex-1 text-left"
        >
          <span className={cn('block truncate text-sm font-medium', selected && 'text-accent')}>
            {batch.label}
          </span>
          <span className="block text-xs text-muted">
            {batch.status === 'done'
              ? `${pct(batch.win_rate ?? 0)} wins · ${batch.duration_s?.toFixed(1)} s`
              : batch.status === 'stopped'
                ? 'stopped: budget reached'
                : batch.status}
            {llm && (batch.cost_usd ?? 0) > 0 && ` · ${usd(batch.cost_usd ?? 0)}`}
            {batch.stale && batch.status === 'done' && ' · book changed since'}
          </span>
        </button>
        {onCompare && (
          <Button
            size="icon"
            variant="ghost"
            aria-label={`Compare with ${batch.label}`}
            aria-pressed={comparing}
            onClick={onCompare}
            className={cn(comparing && 'text-accent')}
          >
            <GitCompare className="size-4" />
          </Button>
        )}
        {resumable && (
          <Button
            size="icon"
            variant="ghost"
            aria-label={`Resume ${batch.label}`}
            title="Play the remaining runs"
            disabled={resume.isPending}
            onClick={() =>
              overBudget ? setAsking(true) : resume.mutate({ id: batch.id, budget: null })
            }
          >
            <Play className="size-4" />
          </Button>
        )}
        {active ? (
          <Button
            size="icon"
            variant="ghost"
            aria-label="Stop"
            onClick={() => batch.job_id && cancel.mutate(batch.job_id)}
          >
            <Square className="size-4" />
          </Button>
        ) : (
          <Button
            size="icon"
            variant="ghost"
            aria-label={`Delete ${batch.label}`}
            onClick={onDelete}
          >
            <Trash2 className="size-4" />
          </Button>
        )}
      </div>
      {asking && resumable && (
        <form
          aria-label={`Resume ${batch.label}`}
          className="mt-2 flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (!budgetOk) return
            resume.mutate(
              { id: batch.id, budget: newBudget },
              { onSuccess: () => setAsking(false) },
            )
          }}
        >
          <label className="text-xs text-muted">
            New budget (USD), more than {usd(spent)} spent
            <NumberInput
              min={0}
              step={0.5}
              allowEmpty
              autoFocus
              value={newBudget}
              onCommit={setNewBudget}
              className="mt-0.5 w-32"
            />
          </label>
          <Button size="sm" type="submit" disabled={!budgetOk || resume.isPending}>
            Resume
          </Button>
          <Button size="sm" type="button" variant="ghost" onClick={() => setAsking(false)}>
            Cancel
          </Button>
        </form>
      )}
      {resume.error && <p className="mt-1 text-xs text-danger">{resume.error.message}</p>}
      {active && (
        <div
          role="progressbar"
          aria-label={`${batch.label} progress`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
          className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-2"
        >
          <div
            className="h-full rounded-full bg-accent transition-[width]"
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      )}
    </li>
  )
}

type Persona = 'cautious' | 'reckless' | 'completionist' | 'role-player'
const PERSONAS: { value: Persona; label: string; hint: string }[] = [
  { value: 'cautious', label: 'Cautious', hint: 'Avoids fights and gambles, keeps its health up.' },
  { value: 'reckless', label: 'Reckless', hint: 'Takes fights, gambles and risky shortcuts.' },
  {
    value: 'completionist',
    label: 'Completionist',
    hint: 'Explores side paths and takes every item.',
  },
  { value: 'role-player', label: 'Role-player', hint: 'Does what the hero would do in the story.' },
]
/** Same caps as the backend: every LLM step is a paid call. */
const LLM_RUNS = 200
const LLM_STEPS = 400

function NewBatch({
  bookId,
  tiers,
  defaultTier,
  onCreated,
}: {
  bookId: string
  tiers: { key: string; label: string }[]
  defaultTier: string
  onCreated: (id: string) => void
}) {
  const bots = useBots()
  const providers = useProviders()
  const create = useCreateBatch(bookId)
  const [tier, setTier] = useState(defaultTier)
  const [kind, setKind] = useState<'bot' | 'llm'>('bot')
  const [bot, setBot] = useState<BotName>('random')
  const [providerId, setProviderId] = useState<string | null>(null)
  const [model, setModel] = useState<string | null>(null)
  const [persona, setPersona] = useState<Persona>('cautious')
  const [budget, setBudget] = useState<number | null>(1)
  const [runs, setRuns] = useState(1000)
  const [seed, setSeed] = useState(1)
  const [maxSteps, setMaxSteps] = useState(500)
  const [label, setLabel] = useState('')
  const llm = kind === 'llm'
  const enabled = (providers.data ?? []).filter((p) => p.enabled)
  const provider = enabled.find((p) => p.id === providerId) ?? enabled[0]
  const modelIds = (provider?.models ?? []).map((m) => String(m.id))
  const modelId = model && modelIds.includes(model) ? model : (modelIds[0] ?? null)
  const maxRuns = llm ? LLM_RUNS : 20000
  const stepCap = llm ? LLM_STEPS : 5000
  const switchKind = (k: 'bot' | 'llm') => {
    setKind(k)
    // LLM games are paid calls per step: start small.
    if (k === 'llm') {
      setRuns((r) => Math.min(r, 10))
      setMaxSteps((m) => Math.min(m, 200))
    }
  }
  return (
    <section
      aria-label="New batch"
      className="space-y-3 rounded-xl border border-border bg-surface p-4"
    >
      <h2 className="text-sm font-semibold">New batch</h2>
      <div role="radiogroup" aria-label="Player" className="flex gap-1 rounded-lg bg-surface-2 p-1">
        {(['bot', 'llm'] as const).map((k) => (
          <button
            key={k}
            type="button"
            role="radio"
            aria-checked={kind === k}
            onClick={() => switchKind(k)}
            className={cn(
              'flex-1 rounded-md px-2 py-1 text-xs font-medium',
              kind === k ? 'bg-surface shadow-sm' : 'text-muted hover:text-text',
            )}
          >
            {k === 'bot' ? 'Bots' : 'LLM players'}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Tier">
          {(id) => (
            <Select
              id={id}
              value={tier}
              options={tiers.map((t) => ({ value: t.key, label: t.label }))}
              onValueChange={(t) => t && setTier(t)}
            />
          )}
        </Field>
        {llm ? (
          <Field label="Persona">
            {(id) => (
              <Select
                id={id}
                value={persona}
                options={PERSONAS}
                onValueChange={(p) => p && setPersona(p)}
              />
            )}
          </Field>
        ) : (
          <Field label="Bot">
            {(id) => (
              <Select
                id={id}
                value={bot}
                options={(bots.data ?? []).map((b) => ({
                  value: b.name,
                  label: b.name[0]!.toUpperCase() + b.name.slice(1),
                }))}
                onValueChange={(b) => b && setBot(b)}
              />
            )}
          </Field>
        )}
      </div>
      {llm ? (
        enabled.length === 0 ? (
          <p className="text-xs text-muted">
            Add a model provider in{' '}
            <Link to="/settings/llm" className="text-accent hover:underline">
              Settings → Models
            </Link>{' '}
            first.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Provider">
              {(id) => (
                <Select
                  id={id}
                  value={provider?.id ?? null}
                  options={enabled.map((p) => ({ value: p.id, label: p.name }))}
                  onValueChange={setProviderId}
                />
              )}
            </Field>
            <Field label="Model">
              {(id) => (
                <Select
                  id={id}
                  value={modelId}
                  options={modelIds.map((m) => ({ value: m, label: m }))}
                  onValueChange={setModel}
                />
              )}
            </Field>
            {modelIds.length === 0 && (
              <p className="col-span-2 text-xs text-danger">
                {provider?.name} lists no models. Add one in{' '}
                <Link to="/settings/llm" className="underline">
                  Settings → Models
                </Link>
                .
              </p>
            )}
            <Field label="Budget (USD)" hint="Stops starting new steps once spent">
              {(id) => (
                <NumberInput
                  id={id}
                  min={0}
                  step={0.5}
                  allowEmpty
                  placeholder="No cap"
                  value={budget}
                  onCommit={(v) => setBudget(v === null ? null : Math.max(0, v))}
                />
              )}
            </Field>
          </div>
        )
      ) : (
        <p className="text-xs text-muted">{bots.data?.find((b) => b.name === bot)?.description}</p>
      )}
      {llm && (
        <p className="text-xs text-muted">
          {PERSONAS.find((p) => p.value === persona)?.hint} Every step is one model call; each run
          is saved as it finishes, so a stopped batch can be resumed.
        </p>
      )}
      <div className="grid grid-cols-3 gap-3">
        <Field label="Runs">
          {(id) => (
            <NumberInput
              id={id}
              min={1}
              max={maxRuns}
              value={runs}
              onCommit={(v) => v && setRuns(Math.min(maxRuns, Math.max(1, v)))}
            />
          )}
        </Field>
        <Field label="First seed">
          {(id) => (
            <NumberInput id={id} min={0} value={seed} onCommit={(v) => v !== null && setSeed(v)} />
          )}
        </Field>
        <Field label="Max steps">
          {(id) => (
            <NumberInput
              id={id}
              min={10}
              max={stepCap}
              value={maxSteps}
              onCommit={(v) => v && setMaxSteps(Math.min(stepCap, Math.max(10, v)))}
            />
          )}
        </Field>
      </div>
      <Field label="Label" hint="Optional, e.g. “after nerfing the troll”">
        {(id) => <TextInput id={id} value={label} onCommit={setLabel} />}
      </Field>
      <Button
        className="w-full"
        disabled={create.isPending || !tier || (llm && !(provider && modelId))}
        onClick={() =>
          create.mutate(
            {
              tier,
              runs: Math.min(runs, maxRuns),
              seed_base: seed,
              max_steps: Math.min(maxSteps, stepCap),
              label,
              player:
                llm && provider && modelId
                  ? { kind: 'llm', provider_id: provider.id, model: modelId, persona }
                  : { kind: 'bot', bot },
              budget_usd: llm ? budget : null,
            },
            {
              onSuccess: (b) => {
                setLabel('')
                onCreated(b.id)
              },
            },
          )
        }
      >
        {llm ? <Sparkles className="size-4" /> : <Bot className="size-4" />} Run{' '}
        {Math.min(runs, maxRuns).toLocaleString()} games
      </Button>
      {create.error && <p className="text-xs text-danger">{create.error.message}</p>}
    </section>
  )
}

function Coverage({
  bookId,
  tiers,
  defaultTier,
}: {
  bookId: string
  tiers: { key: string; label: string }[]
  defaultTier: string
}) {
  const graph = useBookGraph(bookId)
  const start = useStartCoverage(bookId)
  const cancel = useCancelJob()
  const [tier, setTier] = useState(defaultTier)
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJobStream(jobId)
  const result = job?.status === 'done' ? (job.result as unknown as CoverageResult) : null
  const titles = new globalThis.Map((graph.data?.nodes ?? []).map((n) => [n.id, n.title]))

  return (
    <div className="space-y-4">
      <section
        aria-label="Coverage walk"
        className="space-y-3 rounded-xl border border-border bg-surface p-4"
      >
        <p className="text-sm text-muted">
          Explores every choice, pickup and purchase from every distinct situation, re-rolling dice
          a few times, to find content no reader can reach. Exact stat values are ignored, so
          content gated on precise stats may be missed.
        </p>
        <div className="flex items-end gap-3">
          <Field label="Tier">
            {(id) => (
              <Select
                id={id}
                value={tier}
                options={tiers.map((t) => ({ value: t.key, label: t.label }))}
                onValueChange={(t) => t && setTier(t)}
                className="w-40"
              />
            )}
          </Field>
          <Button
            disabled={start.isPending || isActive(job?.status)}
            onClick={() =>
              start.mutate(
                { tier, max_states: 20000, samples: 4 },
                { onSuccess: (j) => setJobId(j.id) },
              )
            }
          >
            <Map className="size-4" /> Walk the book
          </Button>
          {job && isActive(job.status) && (
            <>
              <span role="status" className="text-sm text-muted tabular-nums">
                Explored {job.progress.toLocaleString()} situations…
              </span>
              <Button size="sm" variant="outline" onClick={() => cancel.mutate(job.id)}>
                <Square className="size-3.5" /> Stop
              </Button>
            </>
          )}
          {job?.status === 'cancelled' && <span className="text-sm text-muted">Stopped.</span>}
          {job?.status === 'failed' && <span className="text-sm text-danger">{job.error}</span>}
        </div>
      </section>
      {result && (
        <section
          aria-label="Coverage result"
          className="space-y-3 rounded-xl border border-border bg-surface p-4"
        >
          <p className="text-lg">
            <span className="font-semibold">
              {result.reached.length} of {result.nodes_total}
            </span>{' '}
            nodes are reachable on {tiers.find((t) => t.key === result.tier)?.label ?? result.tier}
            <span className="text-sm text-muted">
              {' '}
              · {result.states.toLocaleString()} situations explored
            </span>
          </p>
          {result.truncated && (
            <p className="flex items-center gap-2 text-sm text-warning">
              <CircleAlert className="size-4" aria-hidden /> Stopped at the exploration limit; some
              reachable nodes may be listed as unreachable.
            </p>
          )}
          {result.unreached.length === 0 ? (
            <p className="text-sm text-success">Every node can be reached.</p>
          ) : (
            <div>
              <h3 className="mb-1 text-sm font-medium">Unreachable</h3>
              <ul className="columns-2 text-sm">
                {result.unreached.map((id) => (
                  <li key={id}>
                    <Link
                      to={`/story/${bookId}?node=${id}`}
                      className="text-accent hover:underline"
                    >
                      {titles.get(id) ?? id}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-sm text-muted">
            Endings reached:{' '}
            {Object.keys(result.endings)
              .map((id) => titles.get(id) ?? id)
              .join(', ') || 'none'}
            {result.other_endings.length > 0 && ` · also ${result.other_endings.join(', ')}`}
          </p>
        </section>
      )}
    </div>
  )
}

interface CoverageResult {
  tier: string
  states: number
  truncated: boolean
  reached: string[]
  unreached: string[]
  endings: Record<string, string[]>
  other_endings: string[]
  nodes_total: number
}
