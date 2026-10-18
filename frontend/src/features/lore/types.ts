import type { components } from '@/api/schema'

export type LoreType = NonNullable<components['schemas']['LoreUpdate']['type']>

export const LORE_TYPES: { value: LoreType; label: string }[] = [
  { value: 'location', label: 'Location' },
  { value: 'faction', label: 'Faction' },
  { value: 'history', label: 'History' },
  { value: 'glossary', label: 'Glossary' },
  { value: 'other', label: 'Other' },
]
