import { useMemo } from 'react'

import { useEntities, useFlags, useRuleSystems } from '@/api/queries'
import { rulesVocabulary, type Vocabulary } from '@/components/gbx/vocabulary'

/** Formula vocabulary for series-level editors (no book: no node keys). */
export function useSeriesVocab(seriesId: string): Vocabulary {
  const rules = useRuleSystems(seriesId)
  const items = useEntities('items', seriesId)
  const flags = useFlags(seriesId)
  return useMemo(
    () => ({
      bookId: '',
      seriesId,
      ...rulesVocabulary(rules.data?.find((r) => r.is_active)),
      items: (items.data ?? []).map((i) => ({ key: i.key, label: i.name })),
      flags: (flags.data ?? []).map((f) => ({ key: f.flag, label: f.flag })),
      nodes: [],
    }),
    [seriesId, rules.data, items.data, flags.data],
  )
}
