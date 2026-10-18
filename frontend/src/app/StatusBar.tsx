import { ChevronDown, ChevronUp, CircleAlert, CircleX, Info } from 'lucide-react'

import { useHealth, useProblems } from '@/api/queries'
import type { ProblemOut } from '@/api/types'
import { useStoryStore } from '@/features/story/storyStore'
import { Kbd } from '@/components/ui/kbd'
import { cn, modKey } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'

import { useCurrentBookId } from './useCurrentBook'

const SEVERITY_ICON = { error: CircleX, warning: CircleAlert, info: Info } as const
const SEVERITY_CLASS = { error: 'text-danger', warning: 'text-warning', info: 'text-info' } as const

/** Bottom status bar with the collapsible Problems panel for the open book. */
export function StatusBar() {
  const { problemsOpen, toggleProblems } = useUiStore()
  const bookId = useCurrentBookId()
  const problems = useProblems(bookId)
  const counts = problems.data?.counts ?? { errors: 0, warnings: 0, info: 0 }
  const { openNode, reveal } = useStoryStore()
  const go = (p: ProblemOut) => {
    if (!p.node_id) return
    openNode(p.node_id, p.choice_id ? 'choices' : 'beat', p.choice_id ?? null)
    reveal(p.node_id)
  }

  return (
    <footer className="border-t border-border bg-surface">
      {problemsOpen && (
        <section
          id="problems-panel"
          aria-label="Problems"
          className="h-48 overflow-auto border-b border-border"
        >
          {!bookId ? (
            <p className="px-4 py-3 text-muted">Open a book to see its problems.</p>
          ) : !problems.data?.problems.length ? (
            <p className="px-4 py-3 text-muted">No problems found.</p>
          ) : (
            <ul>
              {problems.data.problems.map((p, i) => {
                const Icon = SEVERITY_ICON[p.severity]
                return (
                  <li key={i}>
                    <button
                      type="button"
                      onClick={() => go(p)}
                      disabled={!p.node_id}
                      className="flex w-full items-start gap-2 px-4 py-1.5 text-left text-sm hover:bg-surface-2 disabled:cursor-default disabled:hover:bg-transparent"
                    >
                      <Icon
                        className={cn('mt-0.5 size-4 shrink-0', SEVERITY_CLASS[p.severity])}
                        aria-label={p.severity}
                      />
                      <span className="min-w-0 flex-1">{p.message}</span>
                      <span className="shrink-0 font-mono text-xs text-muted">{p.code}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      )}
      <div className="flex h-7 items-center gap-4 px-3 text-xs text-muted">
        <button
          type="button"
          onClick={toggleProblems}
          aria-expanded={problemsOpen}
          aria-controls="problems-panel"
          title={`Toggle problems panel (${modKey}+J)`}
          className="flex items-center gap-3 rounded px-1 hover:text-text"
        >
          <span className="flex items-center gap-1">
            <CircleX className="size-3.5 text-danger" aria-hidden />
            {counts.errors}
            <span className="sr-only">errors</span>
          </span>
          <span className="flex items-center gap-1">
            <CircleAlert className="size-3.5 text-warning" aria-hidden />
            {counts.warnings}
            <span className="sr-only">warnings</span>
          </span>
          <span className="flex items-center gap-1">
            <Info className="size-3.5 text-info" aria-hidden />
            {counts.info}
            <span className="sr-only">info</span>
          </span>
          {problemsOpen ? (
            <ChevronDown className="size-3.5" aria-hidden />
          ) : (
            <ChevronUp className="size-3.5" aria-hidden />
          )}
        </button>
        <span className="hidden items-center gap-1 sm:flex">
          <Kbd>{modKey} K</Kbd> commands
        </span>
        <BackendStatus />
      </div>
    </footer>
  )
}

function BackendStatus() {
  const health = useHealth()
  const ok = health.data?.status === 'ok'
  const label = health.isPending
    ? 'Connecting…'
    : ok
      ? `Connected · v${health.data?.version}`
      : health.data
        ? 'Backend degraded'
        : 'Backend unreachable'
  return (
    <span role="status" className="ml-auto flex items-center gap-1.5">
      <span
        aria-hidden
        className={cn(
          'size-2 rounded-full',
          health.isPending ? 'bg-muted' : ok ? 'bg-success' : 'bg-danger',
        )}
      />
      {label}
    </span>
  )
}
