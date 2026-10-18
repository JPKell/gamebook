import { CircleAlert, CircleX, Plus, Search } from 'lucide-react'
import { type ReactNode, useState } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface ListRow {
  id: string
  title: string
  subtitle?: string
  /** Right-aligned detail, e.g. a quantity. */
  aside?: ReactNode
  group?: string
  errors?: number
  warnings?: number
}

/** Searchable list on the left, editor on the right. */
export function MasterDetail({
  label,
  rows,
  selectedId,
  onSelect,
  onCreate,
  createLabel,
  detail,
  empty,
  loading = false,
}: {
  label: string
  rows: ListRow[]
  selectedId: string | null
  onSelect: (id: string) => void
  onCreate: (name: string) => void
  createLabel: string
  detail: ReactNode
  empty: ReactNode
  loading?: boolean
}) {
  const [q, setQ] = useState('')
  const shown = rows.filter((r) =>
    `${r.title} ${r.subtitle ?? ''}`.toLowerCase().includes(q.trim().toLowerCase()),
  )
  const groups = new Map<string, ListRow[]>()
  for (const r of shown) groups.set(r.group ?? '', [...(groups.get(r.group ?? '') ?? []), r])
  return (
    <div className="grid min-h-0 flex-1 grid-cols-[minmax(240px,320px)_minmax(0,1fr)] gap-4">
      <aside
        aria-label={label}
        className="flex min-h-0 flex-col rounded-xl border border-border bg-surface"
      >
        <div className="space-y-2 border-b border-border p-3">
          <div className="relative">
            <Search
              className="pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2 text-muted"
              aria-hidden
            />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={`Search ${label.toLowerCase()}…`}
              aria-label={`Search ${label.toLowerCase()}`}
              className="h-8 w-full rounded-md border border-border bg-bg pl-8 text-sm focus:border-accent focus:outline-none"
            />
          </div>
          <Button
            size="sm"
            className="w-full"
            onClick={() => {
              const name = window.prompt(`${createLabel}: name`)?.trim()
              if (name) onCreate(name)
            }}
          >
            <Plus className="size-4" /> {createLabel}
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto p-2">
          {loading ? (
            <p className="p-2 text-sm text-muted">Loading…</p>
          ) : rows.length === 0 ? (
            <p className="p-2 text-sm text-muted">Nothing yet.</p>
          ) : (
            shown.length === 0 && <p className="p-2 text-sm text-muted">No matches.</p>
          )}
          {[...groups.entries()].map(([group, items]) => (
            <div key={group} className="mb-2">
              {group && (
                <div className="px-2 pt-1 pb-1 text-xs font-medium tracking-wide text-muted uppercase">
                  {group}
                </div>
              )}
              <ul>
                {items.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(r.id)}
                      aria-current={r.id === selectedId ? 'true' : undefined}
                      className={cn(
                        'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm',
                        r.id === selectedId ? 'bg-accent/12 text-accent' : 'hover:bg-surface-2',
                      )}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{r.title}</span>
                        {r.subtitle && (
                          <span className="block truncate text-xs text-muted">{r.subtitle}</span>
                        )}
                      </span>
                      {r.errors ? (
                        <CircleX
                          className="size-4 shrink-0 text-danger"
                          role="img"
                          aria-label={`${r.errors} errors`}
                        />
                      ) : r.warnings ? (
                        <CircleAlert
                          className="size-4 shrink-0 text-warning"
                          role="img"
                          aria-label={`${r.warnings} warnings`}
                        />
                      ) : null}
                      {r.aside}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </aside>
      <section className="min-h-0 overflow-auto">
        {selectedId ? detail : loading ? null : empty}
      </section>
    </div>
  )
}
