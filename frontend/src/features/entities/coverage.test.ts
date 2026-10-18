import { describe, expect, it } from 'vitest'

import { coverage, fmtRanges } from './coverage'

describe('coverage', () => {
  it('finds gaps and overlaps within the dice range', () => {
    const c = coverage(
      [
        { lo: 1, hi: 2 },
        { lo: 2, hi: 3 },
        { lo: 6, hi: 6 },
      ],
      [1, 6],
      null,
    )
    expect(fmtRanges(c.gaps)).toBe('4–5')
    expect(fmtRanges(c.overlaps)).toBe('2')
    expect(c.chances).toEqual([null, null, null])
  })

  it('sums probabilities per entry', () => {
    const dist = { '2': 1 / 36, '3': 2 / 36, '7': 6 / 36 }
    const c = coverage(
      [
        { lo: 2, hi: 3 },
        { lo: 7, hi: 7 },
      ],
      [2, 12],
      dist,
    )
    expect(c.chances[0]).toBeCloseTo(3 / 36)
    expect(c.chances[1]).toBeCloseTo(6 / 36)
  })

  it('gives an overlapped roll to the first entry, like the engine', () => {
    const dist = Object.fromEntries([1, 2, 3, 4, 5, 6].map((v) => [String(v), 1 / 6]))
    const c = coverage(
      [
        { lo: 1, hi: 3 },
        { lo: 3, hi: 4 },
      ],
      [1, 6],
      dist,
    )
    expect(c.chances[0]).toBeCloseTo(3 / 6)
    expect(c.chances[1]).toBeCloseTo(1 / 6)
  })

  it('handles huge dice ranges without enumerating them', () => {
    const c = coverage([{ lo: 1, hi: 6 }], [10_000, 60_000], null)
    expect(fmtRanges(c.gaps)).toBe('10000–60000')
    const d = coverage(
      [
        { lo: 0, hi: 30_000 },
        { lo: 20_000, hi: 1e9 },
      ],
      [1, 1e8],
      null,
    )
    expect(d.gaps).toEqual([])
    expect(fmtRanges(d.overlaps)).toBe('20000–30000')
  })

  it('reports full coverage as clean', () => {
    const c = coverage([{ lo: 1, hi: 6 }], [1, 6], null)
    expect(c.gaps).toEqual([])
    expect(c.overlaps).toEqual([])
  })
})
