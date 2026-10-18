import { Flame, X } from 'lucide-react'
import { type ReactNode, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'

import { useBatch } from '@/features/playtest/api'
import type { Summary } from '@/features/playtest/summary'

import { type Heat, HeatContext } from './heat'

/** Provides `?heat=<batch id>` to the canvas and shows which batch is overlaid. */
export function HeatProvider({ bookId, children }: { bookId: string; children: ReactNode }) {
  const [params, setParams] = useSearchParams()
  const batchId = params.get('heat')
  const batch = useBatch(batchId)
  const summary = batch.data?.summary as unknown as Summary | null | undefined
  const heat = useMemo<Heat | null>(
    () =>
      batch.data && summary && batch.data.book_id === bookId
        ? {
            batchId: batch.data.id,
            label: batch.data.label,
            runs: summary.runs,
            visits: summary.node_visits,
            deaths: summary.deaths_by_node,
          }
        : null,
    [batch.data, summary, bookId],
  )
  const clear = () =>
    setParams(
      (p) => {
        p.delete('heat')
        return p
      },
      { replace: true },
    )
  return (
    <HeatContext.Provider value={heat}>
      {heat && (
        <div
          role="status"
          className="flex items-center gap-2 border-b border-border bg-surface px-3 py-1.5 text-xs"
        >
          <Flame className="size-3.5 text-danger" aria-hidden />
          <span>
            Playtest heat: <span className="font-medium">{heat.label}</span> (
            {heat.runs.toLocaleString()} runs) — bars show how many runs visited each node; skulls
            count deaths there.
          </span>
          <Link
            to={`/playtest/${bookId}?batch=${heat.batchId}`}
            className="ml-auto text-accent hover:underline"
          >
            Open dashboard
          </Link>
          <button
            type="button"
            onClick={clear}
            aria-label="Hide heat"
            className="rounded p-0.5 text-muted hover:text-text"
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}
      {children}
    </HeatContext.Provider>
  )
}
