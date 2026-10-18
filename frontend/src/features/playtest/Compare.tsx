import { X } from 'lucide-react'

import { Button } from '@/components/ui/button'

import { type BatchDetail, useBatch } from './api'
import { METRICS, OUTCOME_LABELS, pct, type Summary } from './summary'

function Delta({
  a,
  b,
  fmt,
  pctPoints,
}: {
  a: number
  b: number
  fmt: (v: number) => string
  pctPoints: boolean
}) {
  const d = b - a
  if (Math.abs(d) < 1e-9) return <span className="text-muted">—</span>
  const text = pctPoints ? `${(d * 100).toFixed(1)} pts` : fmt(Math.abs(d))
  return (
    <span className="tabular-nums">
      <span aria-hidden>{d > 0 ? '▲ +' : '▼ −'}</span>
      <span className="sr-only">{d > 0 ? 'up ' : 'down '}</span>
      {pctPoints ? text.replace('-', '') : text}
    </span>
  )
}

/** Two batches side by side: before/after a balance change. */
export function Compare({ a, bId, onClose }: { a: BatchDetail; bId: string; onClose: () => void }) {
  const b = useBatch(bId).data
  const sa = a.summary as unknown as Summary | null
  const sb = b?.summary as unknown as Summary | null | undefined
  if (!sa || !sb || !b) return null
  const isPct = (k: string) => ['win', 'death', 'coverage'].includes(k)
  const outcomes = [...new Set([...Object.keys(sa.outcomes), ...Object.keys(sb.outcomes)])]
  const acts = sa.acts.map((x) => ({
    ...x,
    other: sb.acts.find((y) => y.act_id === x.act_id)?.reached,
  }))

  return (
    <section
      aria-label="Batch comparison"
      className="space-y-3 rounded-xl border border-border bg-surface p-4"
    >
      <header className="flex items-center gap-2">
        <h3 className="font-semibold">Comparison</h3>
        {a.content_hash === b.content_hash && (
          <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-muted">
            same book version
          </span>
        )}
        <Button
          size="icon"
          variant="ghost"
          className="ml-auto"
          aria-label="Close comparison"
          onClick={onClose}
        >
          <X className="size-4" />
        </Button>
      </header>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-muted">
            <th className="text-left font-medium">Metric</th>
            <th className="text-right font-medium">{a.label}</th>
            <th className="text-right font-medium">{b.label}</th>
            <th className="text-right font-medium">Change</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {METRICS.map((m) => (
            <tr key={m.key}>
              <td className="py-1">{m.label}</td>
              <td className="text-right tabular-nums">{m.fmt(m.get(sa))}</td>
              <td className="text-right tabular-nums">{m.fmt(m.get(sb))}</td>
              <td className="text-right">
                <Delta a={m.get(sa)} b={m.get(sb)} fmt={m.fmt} pctPoints={isPct(m.key)} />
              </td>
            </tr>
          ))}
          {outcomes.map((k) => {
            const x = (sa.outcomes[k] ?? 0) / sa.runs
            const y = (sb.outcomes[k] ?? 0) / sb.runs
            return (
              <tr key={`o:${k}`}>
                <td className="py-1 text-muted">Outcome: {OUTCOME_LABELS[k] ?? k}</td>
                <td className="text-right tabular-nums">{pct(x)}</td>
                <td className="text-right tabular-nums">{pct(y)}</td>
                <td className="text-right">
                  <Delta a={x} b={y} fmt={pct} pctPoints />
                </td>
              </tr>
            )
          })}
          {acts.map((act) => {
            const x = act.reached / sa.runs
            const y = act.other != null ? act.other / sb.runs : null
            return (
              <tr key={`a:${act.act_id}`}>
                <td className="py-1 text-muted">Reached {act.title}</td>
                <td className="text-right tabular-nums">{pct(x)}</td>
                <td className="text-right tabular-nums">{y == null ? '—' : pct(y)}</td>
                <td className="text-right">
                  {y == null ? '—' : <Delta a={x} b={y} fmt={pct} pctPoints />}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
