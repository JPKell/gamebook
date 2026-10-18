import { CircleAlert, CircleX } from 'lucide-react'

import type { Problem } from './problems'

export function ProblemList({ problems }: { problems: Problem[] | undefined }) {
  if (!problems?.length) return null
  return (
    <ul
      aria-label="Problems"
      className="space-y-1 rounded-xl border border-border bg-surface p-3 text-sm"
    >
      {problems.map((p, i) => (
        <li key={i} className="flex items-start gap-2">
          {p.severity === 'error' ? (
            <CircleX className="mt-0.5 size-4 shrink-0 text-danger" aria-label="Error" />
          ) : (
            <CircleAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-label="Warning" />
          )}
          <span>{p.message}</span>
        </li>
      ))}
    </ul>
  )
}
