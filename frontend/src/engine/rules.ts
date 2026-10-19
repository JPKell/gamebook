/** Tier inheritance: `effective_tier` from `core/rules/schema.py`. Maps keep definition order. */
import type {
  ClassDef,
  CombatDef,
  ProgressionDef,
  StartingItem,
  StatDef,
  TestDef,
  TierDef,
} from './model'

export interface EffectiveTier {
  key: string
  label: string
  index: number
  stats: Map<string, StatDef>
  tests: Map<string, TestDef>
  skills: Map<string, { key: string; label: string; description: string }>
  classes: Map<string, ClassDef>
  slots: string[]
  combat: CombatDef
  progression: ProgressionDef
  startingItems: StartingItem[]
}

const PROGRESSION_FIELDS = [
  'xp_stat',
  'level_stat',
  'xp_award',
  'xp_to_next',
  'max_level',
  'level_up',
] as const

/** Levelling is on when it has an XP stat, a level stat and the XP for the next level. */
export function progressionEnabled(p: ProgressionDef): boolean {
  return Boolean(p.xp_stat && p.level_stat && p.xp_to_next)
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
  const classes = new Map<string, ClassDef>()
  const progression: Record<string, unknown> = {}
  const startingItems: StartingItem[] = []
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
    startingItems.push(...(t.starting_items ?? []))
    for (const f of PROGRESSION_FIELDS) {
      const v = t.progression?.[f]
      if (v !== null && v !== undefined) progression[f] = v
    }
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
    progression: {
      xp_stat: null,
      level_stat: null,
      xp_award: null,
      xp_to_next: null,
      max_level: null,
      level_up: null,
      ...progression,
    } as ProgressionDef,
    startingItems,
  }
}
