/** Pure helpers for editing a rule-system definition (no React). */
import type { components } from '@/api/schema'

type S = components['schemas']
export type RuleSystemDef = S['RuleSystemDef']
export type TierDef = S['TierDef']
export type StatDef = S['StatDef']
export type TestDef = S['TestDef']
export type SkillDef = S['SkillDef']
export type ClassDef = S['ClassDef']
export type CombatDef = S['CombatDef']
export type ProgressionDef = S['ProgressionDef']
export type StatBonus = S['StatBonus']
export type StartingItem = S['StartingItem']
export type DefList = 'stats' | 'tests' | 'skills' | 'classes'
export type DefOf<L extends DefList> = NonNullable<TierDef[L]>[number]

export function clone<T>(v: T): T {
  return structuredClone(v)
}

export function findTier(def: RuleSystemDef, key: string): TierDef | undefined {
  return def.tiers.find((t) => t.key === key)
}

/** Return a copy of ``def`` with ``fn`` applied to one tier. */
export function updateTier(
  def: RuleSystemDef,
  key: string,
  fn: (tier: TierDef) => void,
): RuleSystemDef {
  const next = clone(def)
  const tier = findTier(next, key)
  if (!tier) throw new Error(`Unknown tier ${key}`)
  fn(tier)
  return next
}

/** Add or replace a keyed definition in a tier (overriding an inherited one). */
export function upsert<L extends DefList>(
  tier: TierDef,
  list: L,
  item: DefOf<L>,
  previousKey?: string,
) {
  const items = (tier[list] ?? []) as DefOf<L>[]
  const at = items.findIndex((d) => d.key === (previousKey ?? item.key))
  if (at >= 0) items[at] = item
  else items.push(item)
  ;(tier as Record<string, unknown>)[list] = items
}

/** Remove a definition from this tier (reverting to the inherited one, if any). */
export function remove(tier: TierDef, list: DefList, key: string) {
  ;(tier as Record<string, unknown>)[list] = ((tier[list] ?? []) as { key: string }[]).filter(
    (d) => d.key !== key,
  )
}

export function slugKey(label: string, taken: Set<string>, upper = false): string {
  let base = label
    .trim()
    .replace(/[^A-Za-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  base = upper ? base.toUpperCase() : base.toLowerCase()
  if (!base || !/^[A-Za-z]/.test(base)) base = `${upper ? 'X' : 'x'}_${base}`.replace(/_+$/, '')
  if (/^d\d+$/i.test(base)) base = `${base}_`
  base = base.slice(0, 60)
  let key = base
  for (let n = 2; taken.has(key); n++) key = `${base}_${n}`
  return key
}

/** Append a tier that inherits from the current last tier. */
export function addTier(def: RuleSystemDef, label: string): { def: RuleSystemDef; key: string } {
  const next = clone(def)
  const key = slugKey(label, new Set(next.tiers.map((t) => t.key)))
  next.tiers.push({ key, label, parent: next.tiers[next.tiers.length - 1]?.key ?? null })
  return { def: next, key }
}

/** Remove a tier; refuses when another tier inherits from it. */
export function removeTier(def: RuleSystemDef, key: string): RuleSystemDef {
  const child = def.tiers.find((t) => t.parent === key)
  if (child) throw new Error(`${child.label} inherits from this tier; change its parent first`)
  if (def.tiers.length === 1) throw new Error('A rule system needs at least one tier')
  return { ...clone(def), tiers: def.tiers.filter((t) => t.key !== key).map(clone) }
}

/** Set (or clear, with null/undefined) one combat field on a tier. */
export function setCombat<K extends keyof CombatDef>(
  tier: TierDef,
  field: K,
  value: CombatDef[K] | null,
) {
  const combat = { ...(tier.combat ?? {}) } as Record<string, unknown>
  if (value === null || value === undefined || value === '') delete combat[field as string]
  else combat[field as string] = value
  tier.combat = combat as CombatDef
}

export function setProgression<K extends keyof ProgressionDef>(
  tier: TierDef,
  field: K,
  value: ProgressionDef[K] | null,
) {
  const p = { ...(tier.progression ?? {}) } as Record<string, unknown>
  if (value === null || value === undefined || value === '') delete p[field as string]
  else p[field as string] = value
  tier.progression = p as ProgressionDef
}

/** Starter levelling: XP and LEVEL stats (added here when no tier has them) and formulas. */
export function addLevelling(tier: TierDef, existingStats: Set<string>) {
  const stats = [...(tier.stats ?? [])]
  if (!existingStats.has('XP'))
    stats.push({ key: 'XP', label: 'Experience', applies_to: ['player'], initial: '0' })
  if (!existingStats.has('LEVEL'))
    stats.push({ key: 'LEVEL', label: 'Level', applies_to: ['player'], initial: '1', min: 1 })
  tier.stats = stats
  tier.progression = {
    xp_stat: 'XP',
    level_stat: 'LEVEL',
    xp_award: 'max(1, 10 + 5 * (enemy_level - level))',
    xp_to_next: '100 * level',
    max_level: 10,
    level_up: [],
    // Definitions from the API carry every field, unset ones as null: keep only set ones.
    ...Object.fromEntries(Object.entries(tier.progression ?? {}).filter(([, v]) => v != null)),
  }
}
