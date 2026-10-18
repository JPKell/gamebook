import {
  addTier,
  remove,
  removeTier,
  setCombat,
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
