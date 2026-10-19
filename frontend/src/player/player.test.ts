import { describe, expect, it } from 'vitest'

import { namesFor, narrate } from '@/engine/narrate'
import PARITY from '@/engine/__fixtures__/parity.json'

import { metSoFar } from './met'
import { loadSlots, saveSlot, deleteSlot } from './saves'
import type { PlayerBook } from './types'
import { open, play } from './useGame'

const corpus = PARITY as unknown as {
  books: Record<string, PlayerBook['bundle']>
  cases: Record<
    string,
    {
      tier: string
      seed: number
      creation: { character_class?: string }
      actions: { type: string; target?: string }[]
    }[]
  >
}
const book = { bundle: corpus.books.engine } as unknown as PlayerBook

describe('playing a saved session', () => {
  it('replays moves to the same place every time', () => {
    const c = corpus.cases.engine!.find((x) => x.actions.length > 5)!
    const session = {
      tier: c.tier,
      seed: c.seed,
      characterClass: c.creation.character_class ?? null,
      moves: c.actions.map((a) => ({ type: a.type, target: a.target ?? null })),
    }
    const a = play(book, session)
    const b = play(book, session)
    expect(a.applied).toBe(c.actions.length)
    expect(a.game.state.node_id).toBe(b.game.state.node_id)
    expect(a.latest.length).toBeGreaterThan(0)
    // Narration reads like the authoring app's player.
    const lines = a.game.log.map((e) => narrate(e, namesFor(a.game))).filter(Boolean)
    expect(lines[0]).toMatch(/^Rolled|^Character created|: \d+$/)
  })

  it('stops at moves that no longer apply', () => {
    const c = corpus.cases.engine![0]!
    const played = play(book, {
      tier: c.tier,
      seed: c.seed,
      characterClass: c.creation.character_class ?? null,
      moves: [{ type: 'choose', target: 'no-such-choice' }],
    })
    expect(played.applied).toBe(0)
  })

  it('tracks what the reader has met for the codex', () => {
    const c = corpus.cases.engine!.find((x) => x.actions.some((a) => a.type === 'attack'))!
    const { game } = play(book, {
      tier: c.tier,
      seed: c.seed,
      characterClass: c.creation.character_class ?? null,
      moves: c.actions.map((a) => ({ type: a.type, target: a.target ?? null })),
    })
    expect(metSoFar(game).enemies.size).toBeGreaterThan(0)
  })
})

describe('save slots', () => {
  it('stores, lists newest first and deletes', () => {
    localStorage.clear()
    const base = {
      tier: 'basic',
      seed: 1,
      characterClass: null,
      moves: [],
      where: 'Hall',
      savedAt: '',
    }
    saveSlot('b1', { ...base, id: 'a', name: 'First' })
    saveSlot('b1', { ...base, id: 'b', name: 'Second' })
    expect(loadSlots('b1').map((s) => s.name)).toEqual(['Second', 'First'])
    deleteSlot('b1', 'b')
    expect(loadSlots('b1').map((s) => s.id)).toEqual(['a'])
    localStorage.setItem('gamebook:b2:slots', '{broken')
    expect(loadSlots('b2')).toEqual([])
  })
})

describe('opening saves', () => {
  const c = corpus.cases.engine![0]!
  const base = { tier: c.tier, seed: c.seed, characterClass: c.creation.character_class ?? null }

  it('drops moves an edited book no longer has, so play can continue', () => {
    const good = c.actions.slice(0, 1).map((a) => ({ type: a.type, target: a.target ?? null }))
    const opened = open(book, {
      ...base,
      moves: [...good, { type: 'choose', target: 'gone' }, ...good],
    })
    expect(opened).toEqual({ session: { ...base, moves: good }, trimmed: 2 })
  })

  it('reports a save for a tier the book no longer has instead of crashing', () => {
    const opened = open(book, { ...base, tier: 'legendary', moves: [] })
    expect('error' in opened && opened.error).toContain('legendary')
  })

  it('ignores damaged slots in storage', () => {
    localStorage.setItem(
      'gamebook:b3:slots',
      JSON.stringify([
        { id: 'x', tier: 'basic', seed: 1 },
        { id: 'y', tier: 'basic', seed: 2 ** 60, moves: [] },
      ]),
    )
    expect(loadSlots('b3')).toEqual([])
  })
})
