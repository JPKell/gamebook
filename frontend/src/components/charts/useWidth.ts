import { useLayoutEffect, useRef, useState } from 'react'

/** Track an element's width (charts render to the container width). */
export function useWidth<T extends HTMLElement>(fallback = 480) {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(fallback)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => setWidth(Math.max(200, Math.floor(el.getBoundingClientRect().width)))
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return { ref, width }
}

/** Clean axis ticks: 0 and ~4 round steps up to max. */
export function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0]
  const raw = max / count
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
  const ticks: number[] = []
  for (let v = 0; v <= max + step * 0.001; v += step) ticks.push(Math.round(v * 1000) / 1000)
  if (ticks[ticks.length - 1]! < max) ticks.push(ticks[ticks.length - 1]! + step)
  return ticks
}

export function compact(n: number): string {
  return n >= 1000 ? `${Math.round(n / 100) / 10}K` : String(n)
}

/** Spread end-label y positions so they're at least ``gap`` px apart. */
export function spreadLabels(ys: number[], gap: number, min: number, max: number): number[] {
  const order = ys.map((y, i) => ({ y, i })).sort((a, b) => a.y - b.y)
  for (let k = 1; k < order.length; k++) {
    order[k]!.y = Math.max(order[k]!.y, order[k - 1]!.y + gap)
  }
  // If we ran off the bottom, shift the stack back up.
  const overflow = order.length ? order[order.length - 1]!.y - max : 0
  if (overflow > 0) for (const o of order) o.y -= overflow
  for (const o of order) o.y = Math.max(min, o.y)
  const out = new Array<number>(ys.length)
  for (const o of order) out[o.i] = o.y
  return out
}
