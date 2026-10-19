import { CircleAlert, Flame, Play } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { BarList } from '@/components/charts/BarList'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/inputs'
import { cn } from '@/lib/utils'

import { type BatchDetail, useRuns } from './api'
import { METRICS, OUTCOME_LABELS, pct, type Summary, usd } from './summary'

type Names = BatchDetail['names']

function Card({
  title,
  children,
  className,
}: {
  title: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section
      aria-label={title}
      className={cn('space-y-3 rounded-xl border border-border bg-surface p-4', className)}
    >
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  )
}

const nodeName = (names: Names, id: string) => names.nodes?.[id] ?? 'Deleted node'

export function Dashboard({
  batch,
  onReplay,
}: {
  batch: BatchDetail
  onReplay: (index: number, step?: number) => void
}) {
  const s = batch.summary as unknown as Summary | null
  if (!s) return null
  const names = batch.names
  const bookId = batch.book_id
  const NodeLink = ({ id }: { id: string }) => (
    <Link to={`/story/${bookId}?node=${id}`} className="text-accent hover:underline">
      {nodeName(names, id)}
    </Link>
  )
  const deaths = Object.values(s.deaths_by_node).reduce((a, b) => a + b, 0)

  return (
    <div className="space-y-4">
      {batch.stale && (
        <p
          role="status"
          className="flex items-center gap-2 rounded-lg border border-warning/40 bg-warning/8 p-3 text-sm"
        >
          <CircleAlert className="size-4 text-warning" aria-hidden />
          The book or its rules have changed since this batch ran. Numbers and replays reflect the
          version it played.
        </p>
      )}
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {METRICS.filter((m) => m.key !== 'steps90').map((m) => (
          <div key={m.key} className="rounded-xl border border-border bg-surface p-3">
            <dt className="text-xs text-muted">{m.label}</dt>
            <dd className="text-2xl font-semibold tabular-nums">
              {m.fmt(m.get(s))}
              {m.key === 'endings' && (
                <span className="text-sm font-normal text-muted">
                  {' '}
                  / {s.coverage.endings_total}
                </span>
              )}
            </dd>
          </div>
        ))}
        <div className="rounded-xl border border-border bg-surface p-3">
          <dt className="text-xs text-muted">Steps (p90 / max)</dt>
          <dd className="text-2xl font-semibold tabular-nums">
            {s.steps.p90} <span className="text-sm font-normal text-muted">/ {s.steps.max}</span>
          </dd>
        </div>
      </dl>

      <div className="flex flex-wrap gap-2">
        <Link
          to={`/story/${bookId}?heat=${batch.id}`}
          className="inline-flex h-7 items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 text-xs font-medium hover:bg-surface-2"
        >
          <Flame className="size-3.5" aria-hidden /> Show heat on the canvas
        </Link>
      </div>

      {s.llm && (
        <Card title="Where players got confused">
          <p className="text-sm text-muted">
            {s.llm.confused_steps} of {s.llm.steps} steps flagged as confusing ·{' '}
            {usd(batch.cost_usd ?? s.llm.cost_usd)} spent
            {s.llm.stopped_runs > 0 && ` · ${s.llm.stopped_runs} run(s) stopped early`}
            {(s.llm.failed_runs ?? 0) > 0 &&
              ` · ${s.llm.failed_runs} run(s) ended by a model error (resume replays them)`}
          </p>
          {s.llm.confusion.length === 0 ? (
            <p className="text-sm">No confusion reported.</p>
          ) : (
            <ul className="space-y-3">
              {s.llm.confusion.map((c) => (
                <li key={c.node_id ?? ''} className="space-y-1 text-sm">
                  <div className="flex items-baseline gap-2">
                    {c.node_id ? (
                      <NodeLink id={c.node_id} />
                    ) : (
                      <span>Before the first section</span>
                    )}
                    <span className="text-xs text-muted tabular-nums">
                      {c.count} step{c.count === 1 ? '' : 's'}
                    </span>
                  </div>
                  <ul className="space-y-0.5 border-l-2 border-warning/40 pl-3 text-muted">
                    {c.notes.map((n) => (
                      <li key={`${n.run}:${n.step}`}>
                        <button
                          type="button"
                          className="text-left hover:text-text"
                          onClick={() => onReplay(n.run, n.step)}
                          aria-label={`Replay run ${n.run + 1} (step ${n.step + 1}): ${n.text}`}
                        >
                          “{n.text}” <span className="text-xs">(run #{n.run + 1})</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Outcomes">
          <BarList
            label="Outcomes"
            rows={Object.entries(s.outcomes).map(([k, n]) => ({
              key: k,
              label: OUTCOME_LABELS[k] ?? k,
              fraction: n / s.runs,
              value: `${pct(n / s.runs)} · ${n}`,
              tone: k === 'error' ? 'critical' : 'default',
            }))}
          />
        </Card>
        <Card title="How far readers get (runs reaching each act)">
          <BarList
            label="Act funnel"
            rows={s.acts.map((a) => ({
              key: a.act_id,
              label: a.title,
              fraction: a.reached / s.runs,
              value: pct(a.reached / s.runs),
            }))}
          />
        </Card>
        <Card title="Deadliest nodes">
          {deaths === 0 ? (
            <p className="text-sm text-muted">Nobody died.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted">
                  <th className="text-left font-medium">Node</th>
                  <th className="text-right font-medium">Deaths</th>
                  <th className="text-right font-medium">Death rate there</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {Object.entries(s.deaths_by_node)
                  .slice(0, 8)
                  .map(([id, n]) => (
                    <tr key={id}>
                      <td className="py-1">
                        <NodeLink id={id} />
                      </td>
                      <td className="text-right tabular-nums">{n}</td>
                      <td className="text-right tabular-nums">
                        {pct(n / Math.max(1, s.node_visits[id] ?? 0))}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card title="Enemies">
          {Object.keys(s.enemies).length === 0 ? (
            <p className="text-sm text-muted">No fights.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted">
                  <th className="text-left font-medium">Enemy</th>
                  <th className="text-right font-medium">Fights</th>
                  <th className="text-right font-medium">Player loses</th>
                  <th className="text-right font-medium">Killed the reader</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {Object.entries(s.enemies)
                  .sort((a, b) => b[1].deaths - a[1].deaths || b[1].losses - a[1].losses)
                  .map(([k, e]) => (
                    <tr key={k}>
                      <td className="py-1">{names.enemies?.[k] ?? k}</td>
                      <td className="text-right tabular-nums">{e.fights}</td>
                      <td className="text-right tabular-nums">
                        {pct(e.losses / Math.max(1, e.fights))}
                      </td>
                      <td className="text-right tabular-nums">{e.deaths}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card title="Items: win-rate lift">
          <p className="text-xs text-muted">
            Win rate of runs that ever held the item minus runs that didn't. Correlation, not cause.
          </p>
          {Object.keys(s.items).length === 0 ? (
            <p className="text-sm text-muted">No items picked up.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted">
                  <th className="text-left font-medium">Item</th>
                  <th className="text-right font-medium">Held by</th>
                  <th className="text-right font-medium">Win rate with</th>
                  <th className="text-right font-medium">Lift</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {Object.entries(s.items)
                  .sort((a, b) => Math.abs(b[1].lift ?? 0) - Math.abs(a[1].lift ?? 0))
                  .map(([k, it]) => (
                    <tr key={k}>
                      <td className="py-1">{names.items?.[k] ?? k}</td>
                      <td className="text-right tabular-nums">{pct(it.held_runs / s.runs, 0)}</td>
                      <td className="text-right tabular-nums">
                        {pct(it.wins_with / Math.max(1, it.held_runs))}
                      </td>
                      <td className="text-right tabular-nums">
                        {it.lift == null
                          ? '—'
                          : `${it.lift > 0 ? '+' : ''}${(it.lift * 100).toFixed(1)} pts`}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card title="Endings">
          <BarList
            label="Endings"
            empty="No authored ending was reached."
            rows={Object.entries(s.endings).map(([id, n]) => ({
              key: id,
              label: nodeName(names, id),
              fraction: n / s.runs,
              value: `${pct(n / s.runs)} · ${n}`,
            }))}
          />
        </Card>
        <Card title={`Never visited (${s.coverage.unvisited.length})`}>
          {s.coverage.unvisited.length === 0 ? (
            <p className="text-sm text-muted">Every node was visited at least once.</p>
          ) : (
            <ul className="columns-2 text-sm">
              {s.coverage.unvisited.map((id) => (
                <li key={id}>
                  <NodeLink id={id} />
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-muted">
            {s.coverage.choices_taken} of {s.coverage.choices_total} choices were taken.
          </p>
        </Card>
        {s.errors.runs > 0 && (
          <Card title="Content errors" className="border-danger/40">
            <p className="text-sm">{s.errors.runs} runs hit content errors, for example:</p>
            <ul className="list-disc pl-5 font-mono text-xs">
              {s.errors.sample.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </Card>
        )}
      </div>
      <RunBrowser batch={batch} onReplay={onReplay} />
    </div>
  )
}

function RunBrowser({
  batch,
  onReplay,
}: {
  batch: BatchDetail
  onReplay: (index: number, step?: number) => void
}) {
  const s = batch.summary as unknown as Summary
  const [outcome, setOutcome] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const runs = useRuns(batch.id, outcome, offset)
  const llm = batch.player.kind === 'llm'
  const total = runs.data?.total ?? 0
  return (
    <Card title="Runs">
      <div className="flex items-center gap-2">
        <Select
          aria-label="Filter runs by outcome"
          value={outcome}
          placeholder="All outcomes"
          options={Object.keys(s.outcomes).map((k) => ({
            value: k,
            label: OUTCOME_LABELS[k] ?? k,
          }))}
          onValueChange={(o) => {
            setOutcome(o)
            setOffset(0)
          }}
          className="w-48"
        />
        <span className="ml-auto text-xs text-muted tabular-nums">
          {total ? `${offset + 1}–${Math.min(total, offset + 25)} of ${total}` : 'No runs'}
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={offset === 0}
          onClick={() => setOffset((o) => Math.max(0, o - 25))}
        >
          Previous
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={offset + 25 >= total}
          onClick={() => setOffset((o) => o + 25)}
        >
          Next
        </Button>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-muted">
            <th className="text-left font-medium">Run</th>
            <th className="text-left font-medium">Outcome</th>
            <th className="text-left font-medium">Ended at</th>
            <th className="text-right font-medium">Steps</th>
            {llm && <th className="text-right font-medium">Confused</th>}
            {llm && <th className="text-right font-medium">Cost</th>}
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {(runs.data?.runs ?? []).map((r) => (
            <tr key={r.index}>
              <td className="py-1 tabular-nums">#{r.index + 1}</td>
              <td>
                {OUTCOME_LABELS[r.outcome] ?? r.outcome}
                {r.death_cause?.startsWith('combat:') && (
                  <span className="text-muted">
                    {' '}
                    · {batch.names.enemies?.[r.death_cause.slice(7)] ?? r.death_cause.slice(7)}
                  </span>
                )}
              </td>
              <td className="truncate">
                {r.last_node_id ? nodeName(batch.names, r.last_node_id) : '—'}
              </td>
              <td className="text-right tabular-nums">{r.steps}</td>
              {llm && <td className="text-right tabular-nums">{r.confused_steps}</td>}
              {llm && <td className="text-right tabular-nums">{usd(r.cost_usd ?? 0)}</td>}
              <td className="text-right">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => onReplay(r.index)}
                  aria-label={`Replay run ${r.index + 1}`}
                >
                  <Play className="size-3.5" /> Replay
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
