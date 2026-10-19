/**
 * Parity: the TypeScript engine replays every golden trace written by the Python
 * engine to the same events and final state (ADR 0006).
 */
import { describe, expect, it } from 'vitest'

import PARITY from './__fixtures__/parity.json'
import { SeededRng } from './gbx/pcg32'
import { replay, type Trace } from './trace'

const GOLDEN = import.meta.glob<Trace>('../../../backend/tests/core/golden/*.json', {
  eager: true,
  import: 'default',
})

/** JSON round trip: drops undefined, normalises -0, matches Python's json. */
const plain = (v: unknown) => JSON.parse(JSON.stringify(v)) as unknown

describe('golden traces', () => {
  const files = Object.entries(GOLDEN)
  it('exist', () => expect(files.length).toBeGreaterThan(0))
  for (const [f, trace] of files) {
    it(`replays ${f.split('/').pop()}`, () => {
      const got = replay(trace)
      expect(plain(got.events)).toEqual(trace.events)
      expect(plain(got.final_state)).toEqual(trace.final_state)
    })
  }
})

describe('PCG32', () => {
  it('matches the Python stream for a known seed', () => {
    const rng = new SeededRng(42)
    // Pinned from gamebook.core.gbx.SeededRng(42).roll(10, 6)
    expect(rng.roll(10, 6)).toEqual(PY_42_10D6)
  })
})

const PY_42_10D6 = [3, 6, 4, 4, 4, 5, 1, 6, 3, 4]

/** Python's json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False). */
function canonical(v: unknown): string {
  if (v === null || typeof v !== 'object') return JSON.stringify(v)
  if (Array.isArray(v)) return `[${v.map(canonical).join(',')}]`
  const keys = Object.keys(v as object).sort()
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonical((v as Record<string, unknown>)[k])}`).join(',')}}`
}

interface Corpus {
  books: Record<string, unknown>
  cases: Record<
    string,
    {
      tier: string
      seed: number
      bot: string
      creation: Trace['creation']
      actions: Trace['actions']
      events: number
      digest: string
      final_state: Record<string, unknown>
    }[]
  >
}

describe('parity corpus (bots over many seeds, incl. content errors)', () => {
  const corpus = PARITY as unknown as Corpus
  for (const [book, cases] of Object.entries(corpus.cases)) {
    for (const c of cases) {
      it(`${book} ${c.tier} seed ${c.seed} (${c.bot})`, async () => {
        const got = replay({
          format: 'gamebook-trace',
          version: 1,
          bundle: corpus.books[book],
          tier: c.tier,
          seed: c.seed,
          creation: c.creation,
          actions: c.actions,
          events: [],
          final_state: {},
        })
        expect(plain(got.final_state)).toEqual(c.final_state)
        expect(got.events.length).toBe(c.events)
        const bytes = new TextEncoder().encode(canonical(plain(got.events)))
        const hash = await crypto.subtle.digest('SHA-256', bytes)
        const digest = [...new Uint8Array(hash)]
          .map((b) => b.toString(16).padStart(2, '0'))
          .join('')
        expect(digest).toBe(c.digest)
      })
    }
  }
})
