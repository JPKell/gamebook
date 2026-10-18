import { useState } from 'react'

import { compact, niceTicks, useWidth } from './useWidth'

const HEIGHT = 180
const PAD = { top: 12, right: 8, bottom: 28, left: 36 }
const MAX_BAR = 24
const GAP = 2
const MAX_BINS = 60

/**
 * Single-series histogram (one hue, no legend — the title names it).
 * Bars: ≤24px, 4px rounded data-end, square at the baseline, 2px gaps.
 */
export function Histogram({
  data,
  label,
  valueLabel,
}: {
  /** value → count */
  data: Record<string, number>
  label: string
  valueLabel: (value: number) => string
}) {
  const { ref, width } = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const entries = Object.entries(data)
    .map(([k, v]) => [Number(k), v] as const)
    .sort((a, b) => a[0] - b[0])
  if (!entries.length)
    return (
      <div ref={ref} className="h-44 text-sm text-muted">
        No data.
      </div>
    )

  // Continuous x axis; wide ranges are grouped into at most MAX_BINS bins.
  const lo = entries[0]![0]
  const hi = entries[entries.length - 1]![0]
  const binWidth = Math.max(1, Math.ceil((hi - lo + 1) / MAX_BINS))
  const bins = Array.from({ length: Math.ceil((hi - lo + 1) / binWidth) }, (_, i) => ({
    lo: lo + i * binWidth,
    hi: lo + (i + 1) * binWidth - 1,
    count: 0,
  }))
  for (const [v, c] of entries) bins[Math.floor((v - lo) / binWidth)]!.count += c
  const values = bins.map((b) => b.lo)
  const counts = new Map(bins.map((b) => [b.lo, b.count]))
  const total = entries.reduce((s, [, c]) => s + c, 0)
  const ticks = niceTicks(Math.max(...bins.map((b) => b.count)))
  const yMax = ticks[ticks.length - 1]!
  const plotW = width - PAD.left - PAD.right
  const plotH = HEIGHT - PAD.top - PAD.bottom
  const band = plotW / values.length
  const barW = Math.max(1, Math.min(MAX_BAR, band - GAP))
  const y = (v: number) => PAD.top + plotH - (v / yMax) * plotH
  const labelEvery = Math.ceil(values.length / Math.max(1, Math.floor(plotW / 28)))
  const hovered = hover !== null ? bins[hover]! : null
  const binLabel = (b: { lo: number; hi: number }) =>
    b.lo === b.hi ? valueLabel(b.lo) : `${valueLabel(b.lo)} – ${valueLabel(b.hi)}`

  return (
    <div ref={ref} className="relative">
      <svg width={width} height={HEIGHT} role="img" aria-label={label} className="block">
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PAD.left}
              x2={width - PAD.right}
              y1={y(t)}
              y2={y(t)}
              stroke="var(--chart-grid)"
            />
            <text
              x={PAD.left - 6}
              y={y(t)}
              dy="0.32em"
              textAnchor="end"
              className="fill-muted text-[10px]"
            >
              {compact(t)}
            </text>
          </g>
        ))}
        {values.map((v, i) => {
          const c = counts.get(v) ?? 0
          const x = PAD.left + i * band + (band - barW) / 2
          const top = y(c)
          const h = PAD.top + plotH - top
          const r = Math.min(4, barW / 2, h)
          return (
            <g key={v}>
              {c > 0 && (
                <path
                  d={`M${x},${top + h} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${top + h} Z`}
                  fill="var(--series-1)"
                  opacity={hover === null || hover === i ? 1 : 0.55}
                />
              )}
              {i % labelEvery === 0 && (
                <text
                  x={x + barW / 2}
                  y={HEIGHT - PAD.bottom + 14}
                  textAnchor="middle"
                  className="fill-muted text-[10px]"
                >
                  {v}
                </text>
              )}
              {/* Hit target: the whole column band. */}
              <rect
                x={PAD.left + i * band}
                y={PAD.top}
                width={band}
                height={plotH}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              />
            </g>
          )
        })}
        <line
          x1={PAD.left}
          x2={width - PAD.right}
          y1={PAD.top + plotH}
          y2={PAD.top + plotH}
          stroke="var(--border)"
        />
      </svg>
      {hovered && hover !== null && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-10 -translate-x-1/2 rounded-md border border-border bg-surface px-2 py-1 text-xs shadow"
          style={{ left: PAD.left + hover * band + band / 2, top: 0 }}
        >
          <div className="font-medium text-text">{binLabel(hovered)}</div>
          <div className="text-muted">
            {hovered.count} fights · {((hovered.count / total) * 100).toFixed(1)}%
          </div>
        </div>
      )}
    </div>
  )
}
