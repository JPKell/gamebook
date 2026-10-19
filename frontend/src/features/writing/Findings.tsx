import { useQueryClient } from '@tanstack/react-query'
import { CircleAlert, Info, ScanSearch } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  type FindingPayload,
  useAssistItems,
  useCheckConsistency,
  useSetAssistStatus,
} from '@/features/assist/api'
import { isActive, useJobStream } from '@/features/playtest/api'
import { cn } from '@/lib/utils'

/** Consistency findings for one section, with a button to (re)check it. */
export function Findings({
  bookId,
  nodeId,
  variantId,
  hasProse,
}: {
  bookId: string
  nodeId: string
  variantId: string
  hasProse: boolean
}) {
  const qc = useQueryClient()
  const items = useAssistItems(bookId, 'finding')
  const check = useCheckConsistency(bookId)
  const status = useSetAssistStatus(bookId)
  const job = useJobStream(
    check.data?.id,
    () => void qc.invalidateQueries({ queryKey: ['book', bookId] }),
  )
  // Only this variant's: each reader path has its own prose and findings.
  const findings = (items.data ?? []).filter(
    (f) =>
      f.node_id === nodeId &&
      f.status === 'open' &&
      (f.payload as unknown as FindingPayload).variant_id === variantId,
  )
  const running = check.isPending || isActive(job?.status)
  return (
    <section
      aria-label="Consistency"
      className="space-y-2 rounded-xl border border-border bg-surface p-3 text-sm"
    >
      <div className="flex items-center gap-2">
        <h3 className="font-semibold">Consistency</h3>
        <Button
          size="sm"
          variant="outline"
          className="ml-auto"
          disabled={!hasProse || running}
          title={hasProse ? undefined : 'Write some prose first'}
          onClick={() => check.mutate({ nodeId })}
        >
          <ScanSearch className="size-4" /> {running ? 'Checking…' : 'Check this section'}
        </Button>
      </div>
      {job?.status === 'failed' && <p className="text-danger">{job.error}</p>}
      {findings.length === 0 ? (
        <p className="text-xs text-muted">
          {job?.status === 'done'
            ? 'No problems found.'
            : 'Checks the prose against lore, what readers have here, and the section before it.'}
        </p>
      ) : (
        <ul className="space-y-2">
          {findings.map((f) => {
            const p = f.payload as unknown as FindingPayload
            const Icon = p.severity === 'warning' ? CircleAlert : Info
            return (
              <li
                key={f.id}
                className={cn(
                  'space-y-1 rounded-lg border p-2',
                  f.outdated ? 'border-border opacity-60' : 'border-warning/40',
                )}
              >
                <div className="flex items-start gap-2">
                  <Icon
                    className={cn(
                      'mt-0.5 size-4 shrink-0',
                      p.severity === 'warning' ? 'text-warning' : 'text-muted',
                    )}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    {p.quote && <q className="block text-xs text-muted italic">{p.quote}</q>}
                    <p>{p.problem}</p>
                    {p.suggestion && <p className="text-xs text-muted">→ {p.suggestion}</p>}
                    {f.outdated && (
                      <p className="text-xs text-muted">The prose has changed since this check.</p>
                    )}
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Dismiss: ${p.problem}`}
                    onClick={() => status.mutate({ id: f.id, status: 'dismissed' })}
                  >
                    Dismiss
                  </Button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
