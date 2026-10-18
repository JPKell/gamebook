import type { ItemUpdate } from './api'

export type Category = NonNullable<ItemUpdate['category']>

export const CATEGORIES: { value: Category; label: string; hint: string }[] = [
  {
    value: 'equipment',
    label: 'Equipment',
    hint: 'Modifiers apply while equipped (or carried, if the tier has no slots).',
  },
  {
    value: 'consumable',
    label: 'Consumable',
    hint: 'Used up: runs its use effects, then one is removed.',
  },
  { value: 'key', label: 'Key item', hint: 'Unlocks choices through conditions like has(item).' },
  { value: 'treasure', label: 'Treasure', hint: 'Worth something in shops; no other effect.' },
]
