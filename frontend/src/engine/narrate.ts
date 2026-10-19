/** Plain-English lines for engine events: a port of `core/engine/narrate.py`. */
import type { Game, GameEvent } from './game'

const ENDING_LABELS: Record<string, string> = {
  victory: 'Victory',
  death: 'Death',
  dead_end: 'Dead end',
  defeated: 'Defeated',
  stuck: 'Stuck',
}

export interface Names {
  nodes: Record<string, string>
  items: Record<string, string>
  stats: Record<string, string>
  tests: Record<string, string>
  skills: Record<string, string>
  enemies: Record<string, string>
}

export function namesFor(game: Game): Names {
  const { book, tier } = game
  return {
    nodes: Object.fromEntries(book.nodes.map((n) => [n.id, n.title])),
    items: Object.fromEntries(book.items.map((i) => [i.key, i.name])),
    stats: Object.fromEntries([...tier.stats].map(([k, s]) => [k, s.label])),
    tests: Object.fromEntries([...tier.tests].map(([k, t]) => [k, t.label])),
    skills: Object.fromEntries([...tier.skills].map(([k, s]) => [k, s.label])),
    enemies: Object.fromEntries(book.enemies.map((e) => [e.key, e.name])),
  }
}

export function enemyName(names: Names, key: string): string {
  const [base = key, n] = key.split('#', 2)
  const name = names.enemies[base] ?? base
  return n ? `${name} ${n}` : name
}

const signed = (n: number) => (n > 0 ? `+${n}` : String(n))
/** Python str.capitalize(). */
const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()

export function narrate(e: GameEvent, names: Names): string | null {
  const d = e as Record<string, unknown> & GameEvent
  const stat = names.stats[String(d.stat)] ?? String(d.stat)
  const item = names.items[String(d.item)] ?? String(d.item)
  switch (e.type) {
    case 'character_created': {
      const parts = Object.entries(d.stats as Record<string, number>).map(
        ([k, v]) => `${names.stats[k] ?? k} ${v}`,
      )
      const who = d.class ? ` (${String(d.class)})` : ''
      return `Character created${who}: ` + parts.join(', ')
    }
    case 'roll': {
      const faces = (d.faces as number[]) ?? []
      if (!faces.length && !d.forced) return `${capitalize(String(d.purpose))}: ${String(d.total)}`
      const how = faces.length > 1 ? faces.join(' + ') + ' = ' : ''
      return `Rolled ${String(d.expr)} for ${String(d.purpose)}: ${how}${String(d.total)}${d.forced ? ' (forced)' : ''}`
    }
    case 'enter':
    case 'action':
    case 'outcome':
      return null
    case 'effect':
      switch (d.op) {
        case 'modify':
          return d.change ? `${stat} ${signed(d.change as number)} (now ${String(d.value)})` : null
        case 'set':
          return `${stat} set to ${String(d.value)}`
        case 'give':
          return d.qty ? `Gained ${item} x${String(d.qty)}` : null
        case 'take':
          return d.qty ? `Lost ${item} x${String(d.qty)}` : null
        case 'equip':
          return `Equipped ${item}`
        case 'set_flag':
          return `Codeword noted: ${String(d.flag)}`
        case 'clear_flag':
          return `Codeword removed: ${String(d.flag)}`
        case 'learn':
          return `Learned ${names.skills[String(d.skill)] ?? String(d.skill)}`
      }
      return null
    case 'test':
      return `${names.tests[String(d.test)] ?? String(d.test)}: ${d.success ? 'success' : 'failure'} (rolled ${String(d.roll)})`
    case 'table':
      return `Random table ${String(d.table)}: rolled ${String(d.roll)} → ${String(d.result ?? 'no result')}`
    case 'combat_start':
      return (
        'Combat begins: ' +
        (d.enemies as { key: string; level: number }[])
          .map((x) => `${enemyName(names, x.key)} (level ${x.level})`)
          .join(', ')
      )
    case 'combat_round': {
      const foe = enemyName(names, String(d.enemy))
      const head = `Round ${String(d.round)} vs ${foe}: you ${String(d.player_attack)}, ${foe} ${String(d.enemy_attack)}`
      if (d.hit === 'enemy')
        return `${head} — you hit for ${String(d.damage)} (${String(d.remaining)} left)`
      if (d.hit === 'player')
        return `${head} — you take ${String(d.damage)} (${String(d.remaining)} left)`
      return `${head} — no damage`
    }
    case 'enemy_defeated':
      return `${enemyName(names, String(d.enemy))} is defeated`
    case 'combat_end':
      return (
        (
          { win: 'You won the fight', lose: 'You lost the fight', flee: 'You fled' } as Record<
            string,
            string
          >
        )[String(d.outcome)] ?? `Combat over: ${String(d.outcome)}`
      )
    case 'combat_stalemate':
      return `Stalemate after ${String(d.rounds)} rounds`
    case 'combat_skipped':
      return 'No enemies appeared'
    case 'combat_unconfigured':
      return 'The rules have no combat procedure; the fight is skipped'
    case 'item_taken':
      return d.qty ? `Took ${item} x${String(d.qty)}` : `Couldn't carry more ${item}`
    case 'item_bought':
      return `Bought ${item} for ${String(d.price)}`
    case 'item_sold':
      return `Sold ${item} for ${String(d.price)}`
    case 'item_used':
      return `Used ${item}`
    case 'equipped':
      return `Equipped ${item}`
    case 'unequipped':
      return `Unequipped ${item}`
    case 'game_over': {
      const label = ENDING_LABELS[String(d.ending)] ?? String(d.ending)
      return label + (d.reason ? ` — ${String(d.reason)}` : '')
    }
    case 'error':
      return `Content error in ${String(d.where)}: ${String(d.message)}`
  }
  return null
}
