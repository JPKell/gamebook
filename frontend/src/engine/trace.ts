/** Golden-trace replay (format "gamebook-trace", see `core/engine/trace.py`). */
import { type Creation, Game, type GameEvent, stateToDict } from './game'
import { readBundle } from './model'

export interface Trace {
  format: 'gamebook-trace'
  version: number
  bundle: unknown
  tier: string
  seed: number
  creation?: Creation
  actions: { type: string; target?: string }[]
  events: GameEvent[]
  final_state: Record<string, unknown>
}

export function replay(trace: Trace): {
  events: GameEvent[]
  final_state: Record<string, unknown>
} {
  if (trace.format !== 'gamebook-trace') throw new Error('Not a gamebook trace')
  const game = new Game(readBundle(trace.bundle), trace.tier, trace.seed)
  game.start(trace.creation ?? {})
  for (const a of trace.actions) game.step({ type: a.type as never, target: a.target ?? null })
  return { events: game.log, final_state: stateToDict(game.state) }
}
