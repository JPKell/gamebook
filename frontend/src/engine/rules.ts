/** Tier inheritance: `effective_tier` from `core/rules/schema.py`. Maps keep definition order. */
import type { CombatDef, StatDef, TestDef, TierDef } from './model'

export interface EffectiveTier {
  key: string
  label: string
  index: number
  stats: Map<string, StatDef>
  tests: Map<string, TestDef>
  skills: Map<string, { key: string; label: string; description: string }>
  classes: Map<string, { key: string; label: string; description: string; skills: string[] }>
  slots: string[]
  combat: CombatDef
}

export function tierChain(tiers: TierDef[], key: string): TierDef[] {
  const byKey = new Map(tiers.map((t) => [t.key, t]))
  if (!byKey.has(key)) throw new Error(`Unknown tier '${key}'`)
  const chain: TierDef[] = []
  const seen = new Set<string>()
  let cur: string | null = key
  while (cur !== null) {
    if (seen.has(cur)) throw new Error(`Tier '${key}' has a cyclic parent chain`)
    const t = byKey.get(cur)
    if (!t) throw new Error(`Tier '${chain[chain.length - 1]!.key}' has unknown parent '${cur}'`)
    seen.add(cur)
    chain.push(t)
    cur = t.parent ?? null
  }
  return chain.reverse()
}

const COMBAT_FIELDS = [
  'player_attack',
  'enemy_attack',
  'damage',
  'damage_stat',
  'multi_enemy',
  'flee_allowed',
  'flee_cost',
] as const

export function effectiveTier(tiers: TierDef[], key: string): EffectiveTier {
  const chain = tierChain(tiers, key)
  const stats = new Map<string, StatDef>()
  const tests = new Map<string, TestDef>()
  const skills = new Map<string, { key: string; label: string; description: string }>()
  const classes = new Map<
    string,
    { key: string; label: string; description: string; skills: string[] }
  >()
  const slots: string[] = []
  const combat: Record<string, unknown> = {}
  const hooks: string[] = []
  for (const t of chain) {
    for (const s of t.stats) stats.set(s.key, s)
    for (const x of t.tests) tests.set(x.key, x)
    for (const x of t.skills) skills.set(x.key, x)
    for (const x of t.classes) classes.set(x.key, x)
    for (const s of t.slots) if (!slots.includes(s)) slots.push(s)
    for (const f of COMBAT_FIELDS) {
      const v = t.combat[f]
      if (v !== null && v !== undefined) combat[f] = v
    }
    hooks.push(...(t.combat.damage_hooks ?? []))
  }
  const top = chain[chain.length - 1]!
  return {
    key: top.key,
    label: top.label,
    index: tiers.findIndex((t) => t.key === top.key),
    stats,
    tests,
    skills,
    classes,
    slots,
    combat: {
      player_attack: null,
      enemy_attack: null,
      damage: null,
      damage_stat: null,
      multi_enemy: null,
      flee_allowed: null,
      flee_cost: null,
      ...combat,
      damage_hooks: hooks,
    } as CombatDef,
  }
}
