import { ChevronDown, ChevronUp, CircleAlert, CircleX, Info } from 'lucide-react'

import { useHealth } from '@/api/queries'
import { Kbd } from '@/components/ui/kbd'
import { cn, modKey } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'

/** Bottom status bar with the collapsible Problems panel (validation lands in Phase 1). */
export function StatusBar() {
  const { problemsOpen, toggleProblems } = useUiStore()
  const counts = { errors: 0, warnings: 0, info: 0 }

  return (
    <footer className="border-t border-border bg-surface">
      {problemsOpen && (
        <section
          id="problems-panel"
          aria-label="Problems"
          className="h-40 overflow-auto border-b border-border px-4 py-3 text-muted"
        >
          No problems detected. Validation results will appear here.
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
