import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from '@/api/client'
import { useRuleSystems } from '@/api/queries'
import { useUiStore } from '@/stores/ui'

/**
 * The UI tier when the active rules have it, else null (the server's default,
 * the highest tier). Undefined while the rules are loading.
 */
export function useDigestTier(seriesId: string): string | null | undefined {
  const uiTier = useUiStore((s) => s.tier)
  const systems = useRuleSystems(seriesId)
  if (systems.isPending) return undefined
  const tiers = systems.data?.find((r) => r.is_active)?.definition.tiers ?? []
  return tiers.some((t) => t.key === uiTier) ? uiTier : null
}

/**
 * State digest of one node, read from the whole-book digest: one request per
 * book change (it lives under ['book', id]) however many nodes are selected.
 */
export function useNodeDigest(bookId: string, nodeId: string, tier: string | null | undefined) {
  return useQuery({
    queryKey: ['book', bookId, 'digest', tier],
    queryFn: () =>
      unwrap(
        api.GET('/api/books/{book_id}/digest', {
          params: { path: { book_id: bookId }, query: { tier: tier ?? null } },
        }),
      ),
    enabled: tier !== undefined,
    select: (d) => d.nodes[nodeId],
  })
}

/** The book's outline (acts with beats). */
export function useOutline(bookId: string | undefined) {
  return useQuery({
    queryKey: ['book', bookId ?? '', 'outline'],
    queryFn: () =>
      unwrap(api.GET('/api/books/{book_id}/outline', { params: { path: { book_id: bookId! } } })),
    enabled: !!bookId,
  })
}
