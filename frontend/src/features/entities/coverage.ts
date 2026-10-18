export interface Range {
  lo: number
  hi: number
}

export interface Coverage {
  /** Rolls no entry covers (inclusive ranges). */
  gaps: Range[]
  /** Rolls more than one entry covers. */
  overlaps: Range[]
  /** Entry index → probability the engine picks it (needs a distribution). */
  chances: (number | null)[]
}

/**
 * Which dice results a table's entries cover. `rollRange` is the dice's
 * min..max; `dist` maps each result to its probability when known. Like the
 * engine, the first entry covering a roll wins it.
 */
export function coverage(
  entries: Range[],
  rollRange: number[] | null,
  dist: Record<string, number> | null,
): Coverage {
  const chances = entries.map(() => (dist ? 0 : null))
  if (dist)
    for (const [k, p] of Object.entries(dist)) {
      const v = Number(k)
      const i = entries.findIndex((e) => e.lo <= v && v <= e.hi)
      if (i >= 0) chances[i]! += p
    }
  if (!rollRange || rollRange.length < 2) return { gaps: [], overlaps: [], chances }
  const [min, max] = rollRange as [number, number]
  // Sweep the boundaries (O(entries²)), so huge dice ranges cost nothing extra.
  const cuts = new Set([min, max + 1])
  for (const e of entries) {
    if (e.lo > min && e.lo <= max) cuts.add(e.lo)
    if (e.hi + 1 > min && e.hi + 1 <= max) cuts.add(e.hi + 1)
  }
  const points = [...cuts].sort((a, b) => a - b)
  const gaps: Range[] = []
  const overlaps: Range[] = []
  const push = (out: Range[], lo: number, hi: number) => {
    const last = out[out.length - 1]
    if (last && last.hi === lo - 1) last.hi = hi
    else out.push({ lo, hi })
  }
  for (let i = 0; i < points.length - 1; i++) {
    const lo = points[i]!
    const hi = points[i + 1]! - 1
    const n = entries.filter((e) => e.lo <= lo && lo <= e.hi).length
    if (n === 0) push(gaps, lo, hi)
    else if (n > 1) push(overlaps, lo, hi)
  }
  return { gaps, overlaps, chances }
}

export const fmtRanges = (rs: Range[]) =>
  rs.map((r) => (r.lo === r.hi ? `${r.lo}` : `${r.lo}–${r.hi}`)).join(', ')
