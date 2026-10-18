import type { ReactNode } from 'react'

export interface BarRow {
  key: string
  label: ReactNode
  /** 0..1 of the bar's full width. */
  fraction: number
  /** Value shown at the end of the row (text tokens, never the bar color). */
  value: ReactNode
  /** Accessible description of the row, e.g. "Act 2: 64% of runs". */
  title?: string
  /** Use the status "critical" token instead of the series color. */
  tone?: 'default' | 'critical'
}

/**
 * Labelled horizontal bars for one measure (single hue, no legend — the
 * heading names it). Thin 10px bars with 4px rounded data ends; the row
 * itself is the hover target.
 */
export function BarList({
  rows,
  label,
  empty = 'No data.',
}: {
  rows: BarRow[]
  label: string
  empty?: string
}) {
  if (!rows.length) return <p className="text-sm text-muted">{empty}</p>
  return (
    <ul aria-label={label} className="space-y-1.5">
      {rows.map((r) => (
        <li
          key={r.key}
          title={r.title}
          className="grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)_auto] items-center gap-3 rounded px-1 text-sm hover:bg-surface-2"
        >
          <span className="truncate">{r.label}</span>
          <span className="h-2.5 rounded-r bg-[var(--chart-grid)]/40" aria-hidden>
            <span
              className="block h-full rounded-r"
              style={{
                width: `${Math.max(0, Math.min(1, r.fraction)) * 100}%`,
                minWidth: r.fraction > 0 ? 2 : 0,
                background: r.tone === 'critical' ? 'var(--danger)' : 'var(--series-1)',
              }}
            />
          </span>
          <span className="text-right text-muted tabular-nums">{r.value}</span>
        </li>
      ))}
    </ul>
  )
}
