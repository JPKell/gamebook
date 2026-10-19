import type { Game } from '@/engine/game'

/** Enemies fought and items held or found so far (codex entries unlock as met). */
export function metSoFar(game: Game): { enemies: Set<string>; items: Set<string> } {
  const enemies = new Set<string>()
  const items = new Set([...game.state.items].filter(([, n]) => n > 0).map(([k]) => k))
  for (const e of game.log) {
    if (e.type === 'combat_start')
      for (const x of e.enemies as { key: string }[]) enemies.add(x.key.split('#')[0]!)
    else if (
      (e.type === 'item_taken' ||
        e.type === 'item_bought' ||
        (e.type === 'effect' && e.op === 'give')) &&
      e.item
    )
      items.add(String(e.item))
  }
  return { enemies, items }
}
