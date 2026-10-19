import {
  addLevelling,
  addTier,
  remove,
  removeTier,
  setCombat,
  setProgression,
  slugKey,
  updateTier,
  upsert,
  type RuleSystemDef,
} from './defs'

const def = (): RuleSystemDef => ({
  tiers: [
    { key: 'basic', label: 'Basic', stats: [{ key: 'SKILL', label: 'Skill' }] },
    { key: 'medium', label: 'Medium', parent: 'basic' },
  ],
})

describe('rule-system edit helpers', () => {
  it('overrides, edits and reverts keyed definitions without mutating the input', () => {
    const original = def()
    const overridden = updateTier(original, 'medium', (t) =>
      upsert(t, 'stats', { key: 'SKILL', label: 'Prowess' }),
    )
    expect(original.tiers[1]!.stats).toBeUndefined()
    expect(overridden.tiers[1]!.stats).toEqual([{ key: 'SKILL', label: 'Prowess' }])
    const renamed = updateTier(overridden, 'medium', (t) =>
      upsert(t, 'stats', { key: 'POWER', label: 'Power' }, 'SKILL'),
    )
    expect(renamed.tiers[1]!.stats).toEqual([{ key: 'POWER', label: 'Power' }])
    const reverted = updateTier(renamed, 'medium', (t) => remove(t, 'stats', 'POWER'))
    expect(reverted.tiers[1]!.stats).toEqual([])
  })

  it('adds tiers inheriting from the last one and protects parents', () => {
    const { def: next, key } = addTier(def(), 'Expert Mode')
    expect(key).toBe('expert_mode')
    expect(next.tiers[2]).toEqual({ key: 'expert_mode', label: 'Expert Mode', parent: 'medium' })
    expect(() => removeTier(next, 'medium')).toThrow(/inherits/)
    expect(removeTier(next, 'expert_mode').tiers.map((t) => t.key)).toEqual(['basic', 'medium'])
    expect(() => removeTier({ tiers: [{ key: 'a', label: 'A' }] }, 'a')).toThrow(/at least one/)
  })

  it('makes valid unique keys', () => {
    expect(slugKey('Test your Luck!', new Set())).toBe('test_your_luck')
    expect(slugKey('Magic Points', new Set(['MAGIC_POINTS']), true)).toBe('MAGIC_POINTS_2')
    expect(slugKey('42', new Set())).toBe('x_42')
    expect(slugKey('d6', new Set())).toBe('d6_')
  })

  it('sets and clears combat fields', () => {
    const tier = def().tiers[1]!
    setCombat(tier, 'damage', '3')
    expect(tier.combat).toEqual({ damage: '3' })
    setCombat(tier, 'damage', '')
    expect(tier.combat).toEqual({})
  })
})

describe('levelling helpers', () => {
  it('sets up XP and LEVEL once, keeping what the tier already has', () => {
    const next = updateTier(def(), 'medium', (t) => addLevelling(t, new Set(['SKILL'])))
    const medium = next.tiers[1]!
    expect(medium.stats!.map((s) => s.key)).toEqual(['XP', 'LEVEL'])
    expect(medium.progression).toMatchObject({ xp_stat: 'XP', level_stat: 'LEVEL', max_level: 10 })
    const again = updateTier(next, 'medium', (t) => addLevelling(t, new Set(['XP', 'LEVEL'])))
    expect(again.tiers[1]!.stats).toHaveLength(2)
  })

  it('fills in unset (null) progression fields from the API', () => {
    const d = def()
    d.tiers[1]!.progression = {
      xp_stat: null,
      level_stat: null,
      xp_award: null,
      xp_to_next: '20 * level',
      max_level: null,
      level_up: null,
    }
    const next = updateTier(d, 'medium', (t) => addLevelling(t, new Set()))
    expect(next.tiers[1]!.progression).toMatchObject({
      xp_stat: 'XP',
      level_stat: 'LEVEL',
      xp_to_next: '20 * level',
    })
  })

  it('clears a progression field so it inherits', () => {
    const next = updateTier(def(), 'medium', (t) => {
      setProgression(t, 'xp_to_next', '50 * level')
      setProgression(t, 'max_level', 5)
      setProgression(t, 'max_level', null)
    })
    expect(next.tiers[1]!.progression).toEqual({ xp_to_next: '50 * level' })
  })
})
