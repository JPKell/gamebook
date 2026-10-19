import { useMemo } from 'react'

import { Game, GameError, type GameEvent } from '@/engine/game'
import { readBundle } from '@/engine/model'

import type { Session } from './saves'
import type { PlayerBook } from './types'

export interface Played {
  game: Game
  /** Events produced by the last move (or by character creation and the start). */
  latest: GameEvent[]
  /** Moves that still applied (fewer than saved when the book changed since). */
  applied: number
}

/** Replay a session's moves from the start; the engine is deterministic, so this is the game. */
export function play(book: PlayerBook, s: Session): Played {
  const game = new Game(readBundle(book.bundle), s.tier, s.seed)
  let latest = game.start({ character_class: s.characterClass })
  let applied = 0
  for (const m of s.moves) {
    try {
      latest = game.step({ type: m.type as never, target: m.target })
      applied += 1
    } catch (e) {
      if (e instanceof GameError) break // a save from an older edition of the book
      throw e
    }
  }
  return { game, latest, applied }
}

export type Opened = { session: Session; trimmed: number } | { error: string }

/**
 * Check a saved session against this edition of the book before playing it. Moves that
 * no longer apply (the book changed since) are dropped, so new moves continue from
 * where the save still holds; a tier or class the book no longer has is an error.
 */
export function open(book: PlayerBook, s: Session): Opened {
  try {
    const { applied } = play(book, s)
    return {
      session: { ...s, moves: s.moves.slice(0, applied) },
      trimmed: s.moves.length - applied,
    }
  } catch (e) {
    return { error: e instanceof Error ? e.message : String(e) }
  }
}

export function useGame(book: PlayerBook, session: Session | null): Played | null {
  return useMemo(() => (session ? play(book, session) : null), [book, session])
}
