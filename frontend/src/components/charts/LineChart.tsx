import { useState } from 'react'

import { spreadLabels, useWidth } from './useWidth'

export interface Series {
  key: string
  label: string
  points: { x: number; y: number }[]
}

const HEIGHT = 240
const PAD = { top: 14, right: 72, bottom: 30, left: 40 }
const COLORS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)']

/**
 * Line chart for 1–3 series sharing one y scale (0–1 shown as %). 2px lines,
 * crosshair tooltip, legend + direct end labels for ≥2 series.
 */
export function LineChart({
  series,
  label,
  xLabel,
  yFormat = (v) => `${Math.round(v * 100)}%`,
  yMax = 1,
}: {
  series: Series[]
  label: string
  xLabel: string
  yFormat?: (v: number) => string
  yMax?: number
}) {
  const { ref, width } = useWidth<HTMLDivElement>()
  const [hoverX, setHoverX] = useState<number | null>(null)
  const xs = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b)
  if (!xs.length)
    return (
      <div ref={ref} className="h-60 text-sm text-muted">
        No data.
      </div>
    )
  const plotW = width - PAD.left - PAD.right
  const plotH = HEIGHT - PAD.top - PAD.bottom
  const x0 = xs[0]!
  const x1 = xs[xs.length - 1]!
  const sx = (x: number) => PAD.left + (x1 === x0 ? plotW / 2 : ((x - x0) / (x1 - x0)) * plotW)
  const sy = (y: number) => PAD.top + plotH - (y / yMax) * plotH
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * yMax)
  const multi = series.length > 1
  const labelEvery = Math.ceil(xs.length / Math.max(1, Math.floor(plotW / 32)))

  const ends = series.map((s) => [...s.points].sort((a, b) => a.x - b.x).at(-1))
  const labelYs = spreadLabels(
    ends.map((p) => (p ? sy(p.y) : 0)),
    13,
    PAD.top,
    PAD.top + plotH,
  )

  const nearest = (clientX: number, rect: DOMRect) => {
    const px = clientX - rect.left
    return xs.reduce(
      (best, x) => (Math.abs(sx(x) - px) < Math.abs(sx(best) - px) ? x : best),
      xs[0]!,
    )
  }

  return (
    <div ref={ref} className="relative">
      {multi && (
        <ul className="mb-2 flex flex-wrap gap-3 text-xs text-muted" aria-label="Legend">
          {series.map((s, i) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded" style={{ background: COLORS[i] }} aria-hidden />
              {s.label}
            </li>
          ))}
        </ul>
      )}
      <svg
        width={width}
        height={HEIGHT}
        role="img"
        aria-label={label}
        className="block"
        onMouseMove={(e) => setHoverX(nearest(e.clientX, e.currentTarget.getBoundingClientRect()))}
        onMouseLeave={() => setHoverX(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PAD.left}
              x2={PAD.left + plotW}
              y1={sy(t)}
              y2={sy(t)}
              stroke="var(--chart-grid)"
            />
            <text
              x={PAD.left - 6}
              y={sy(t)}
              dy="0.32em"
              textAnchor="end"
              className="fill-muted text-[10px]"
            >
              {yFormat(t)}
            </text>
          </g>
        ))}
        {xs.map((x, i) =>
          i % labelEvery === 0 ? (
            <text
              key={x}
              x={sx(x)}
              y={HEIGHT - PAD.bottom + 16}
              textAnchor="middle"
              className="fill-muted text-[10px]"
            >
              {x}
            </text>
          ) : null,
        )}
        <text
          x={PAD.left + plotW / 2}
          y={HEIGHT - 2}
          textAnchor="middle"
          className="fill-muted text-[10px]"
        >
          {xLabel}
        </text>
        {hoverX !== null && (
          <line
            x1={sx(hoverX)}
            x2={sx(hoverX)}
            y1={PAD.top}
            y2={PAD.top + plotH}
            stroke="var(--border)"
          />
        )}
        {series.map((s, i) => {
          const pts = [...s.points].sort((a, b) => a.x - b.x)
          const last = pts[pts.length - 1]
          return (
            <g key={s.key}>
              <path
                d={pts.map((p, j) => `${j ? 'L' : 'M'}${sx(p.x)},${sy(p.y)}`).join(' ')}
                fill="none"
                stroke={COLORS[i]}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {hoverX !== null &&
                pts
                  .filter((p) => p.x === hoverX)
                  .map((p) => (
                    <circle
                      key={p.x}
                      cx={sx(p.x)}
                      cy={sy(p.y)}
                      r={4}
                      fill={COLORS[i]}
                      stroke="var(--surface)"
                      strokeWidth={2}
                    />
                  ))}
              {multi && last && (
                <text
                  x={sx(last.x) + 6}
                  y={labelYs[i]}
                  dy="0.32em"
                  className="fill-text text-[11px]"
                >
                  {s.label}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      {hoverX !== null && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-10 rounded-md border border-border bg-surface px-2 py-1 text-xs shadow"
          style={{ left: Math.min(sx(hoverX) + 8, width - 140), top: multi ? 28 : 4 }}
        >
          <div className="font-medium text-text">
            {xLabel} {hoverX}
          </div>
          {series.map((s, i) => {
            const p = s.points.find((q) => q.x === hoverX)
            return p ? (
              <div key={s.key} className="flex items-center gap-1.5 text-muted">
                <span
                  className="size-2 rounded-full"
                  style={{ background: COLORS[i] }}
                  aria-hidden
                />
                {s.label}: <span className="text-text">{yFormat(p.y)}</span>
              </div>
            ) : null
          })}
        </div>
      )}
    </div>
  )
}
