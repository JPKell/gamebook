import { ChevronLeft, ChevronRight, SkipBack, SkipForward, X } from 'lucide-react'
import { useDeferredValue, useState } from 'react'

import { Button } from '@/components/ui/button'

import { type BatchDetail, useReplay } from './api'
import { Scene, Sheet } from './Player'
import { OUTCOME_LABELS } from './summary'

/** Step through a stored bot run (replayed on the bundle the batch played). */
export function Replay({
  batch,
  index,
  onClose,
}: {
  batch: BatchDetail
  index: number
  onClose: () => void
}) {
  const full = useReplay(batch.id, index, null)
  const total = full.data?.steps ?? 0
  const [step, setStep] = useState<number | null>(null)
  const at = step ?? total
  // Scrubbing the slider asks for the latest position only, not every tick.
  const view = useReplay(batch.id, index, useDeferredValue(step))
  const data = view.data
  const go = (n: number) => setStep(Math.max(0, Math.min(total, n)))
  const ended = full.data?.ended

  return (
    <section
      aria-label={`Replay of run ${index + 1}`}
      className="space-y-4 rounded-xl border border-accent/40 bg-surface p-4"
    >
      <header className="flex flex-wrap items-center gap-3">
        <h3 className="font-semibold">
          Run #{index + 1}
          {ended && (
            <span className="font-normal text-muted"> · {OUTCOME_LABELS[ended] ?? ended}</span>
          )}
        </h3>
        <div className="ml-auto flex items-center gap-1">
          <Button
            size="icon"
            variant="ghost"
            aria-label="First step"
            onClick={() => go(0)}
            disabled={at === 0}
          >
            <SkipBack className="size-4" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            aria-label="Previous step"
            onClick={() => go(at - 1)}
            disabled={at === 0}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <span aria-live="polite" className="w-24 text-center text-sm tabular-nums">
            Step {at} / {total}
          </span>
          <Button
            size="icon"
            variant="ghost"
            aria-label="Next step"
            onClick={() => go(at + 1)}
            disabled={at >= total}
          >
            <ChevronRight className="size-4" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            aria-label="Last step"
            onClick={() => go(total)}
            disabled={at >= total}
          >
            <SkipForward className="size-4" />
          </Button>
          <Button size="icon" variant="ghost" aria-label="Close replay" onClick={onClose}>
            <X className="size-4" />
          </Button>
        </div>
      </header>
      <input
        type="range"
        min={0}
        max={total}
        value={at}
        onChange={(e) => go(Number(e.target.value))}
        aria-label="Replay position"
        className="w-full accent-[var(--accent)]"
      />
      {data && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="space-y-3">
            <Scene view={data} bookId={batch.book_id} turn={at - 1} />
            {at < total && (
              <p className="text-sm text-muted">
                Next, the bot chose:{' '}
                <span className="font-medium text-text">
                  {nextLabel(full.data?.events ?? [], data.actions, at)}
                </span>
              </p>
            )}
          </div>
          <Sheet view={data} />
        </div>
      )}
    </section>
  )
}

type View = NonNullable<ReturnType<typeof useReplay>['data']>

/** The label of the action taken at step ``at``: the full run's action event, named by this step's options. */
function nextLabel(events: View['events'], actions: View['actions'], at: number) {
  const action = events.find((e) => e.type === 'action' && e.turn === at)
  if (!action) return '—'
  const d = action.data as { action: string; target?: string | null }
  return (
    actions.find((a) => a.type === d.action && a.target === (d.target ?? null))?.label ?? d.action
  )
}
