import { ChevronLeft, ChevronRight, CircleHelp, SkipBack, SkipForward, X } from 'lucide-react'
import { useDeferredValue, useState } from 'react'

import { Button } from '@/components/ui/button'

import { type BatchDetail, useReplay } from './api'
import { Scene, Sheet } from './Player'
import { OUTCOME_LABELS } from './summary'

/** Step through a stored run (replayed on the bundle the batch played). */
export function Replay({
  batch,
  index,
  initialStep = null,
  onClose,
}: {
  batch: BatchDetail
  index: number
  /** Open at this step (e.g. where the player got confused) instead of the end. */
  initialStep?: number | null
  onClose: () => void
}) {
  const full = useReplay(batch.id, index, null)
  const total = full.data?.steps ?? 0
  const [step, setStep] = useState<number | null>(initialStep)
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
            {at < total && !data.next_note && (
              <p className="text-sm text-muted">
                Next, the bot chose:{' '}
                <span className="font-medium text-text">
                  {nextLabel(full.data?.events ?? [], data.actions, at)}
                </span>
              </p>
            )}
            {data.next_note && <PlayerNote note={data.next_note as unknown as Note} />}
          </div>
          <Sheet view={data} />
        </div>
      )}
    </section>
  )
}

interface Note {
  option: string
  reasoning: string
  confused: boolean
  confusion: string
}

/** What an LLM player thought at this step, and what it chose. */
function PlayerNote({ note }: { note: Note }) {
  return (
    <section
      aria-label="Player's reasoning"
      className="space-y-1 rounded-lg border border-border bg-surface-2/50 p-3 text-sm"
    >
      <p className="text-muted">
        Next, the player chose: <span className="font-medium text-text">{note.option}</span>
      </p>
      {note.reasoning && <p className="italic">“{note.reasoning}”</p>}
      {note.confused && (
        <p className="flex items-start gap-1.5 text-warning">
          <CircleHelp className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            <span className="font-medium">Confused:</span> {note.confusion || 'no details given'}
          </span>
        </p>
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
