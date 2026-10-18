import { useEntities } from '@/api/queries'

import type { MentionTarget } from './mentions'

export function useMentionTargets(seriesId: string): MentionTarget[] {
  const chars = useEntities('characters', seriesId)
  const lore = useEntities('lore', seriesId)
  return [
    ...(chars.data ?? []).map((c) => ({
      kind: 'character' as const,
      id: c.id,
      key: c.key,
      name: c.name,
    })),
    ...(lore.data ?? []).map((l) => ({
      kind: 'lore' as const,
      id: l.id,
      key: l.key,
      name: l.name,
    })),
  ]
}
