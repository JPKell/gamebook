import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from '@/api/client'
import { useApiMutation } from '@/api/queries'
import type { components } from '@/api/schema'

export type AssistItem = components['schemas']['AssistItemOut']

export interface SuggestionNode {
  ref: string
  title: string
  beat_notes: string
  beat: string
  status: 'pending' | 'accepted' | 'rejected'
  node_id: string | null
  /** Where the backend will place it (so the ghost doesn't jump on accept). */
  x?: number
  y?: number
}
export interface SuggestionChoice {
  from: string
  to: string
  label: string
  status: 'pending' | 'accepted' | 'rejected'
}
export interface SuggestionPayload {
  rationale: string
  notes: string
  nodes: SuggestionNode[]
  choices: SuggestionChoice[]
}
export interface FindingPayload {
  variant_id: string
  variant_label: string
  severity: 'warning' | 'info'
  category: string
  quote: string
  problem: string
  suggestion: string
}
export interface LorePayload {
  target: 'character' | 'lore'
  existing_id: string | null
  existing_key: string | null
  fields: Record<string, string>
  evidence: string
}

/** Assist items live under ['book', id] so book edits and accepts refresh them. */
export const ak = {
  items: (bookId: string, kind: string) => ['book', bookId, 'assist', kind] as const,
}

export function useAssistItems(
  bookId: string | undefined,
  kind: 'finding' | 'suggestion' | 'lore',
) {
  return useQuery({
    queryKey: ak.items(bookId ?? '', kind),
    queryFn: () =>
      unwrap(
        api.GET('/api/books/{book_id}/assist', {
          params: { path: { book_id: bookId! }, query: { kind } },
        }),
      ),
    enabled: !!bookId,
    staleTime: 0,
  })
}

const touched = (bookId: string, seriesId?: string) => [
  ['book', bookId],
  ...(seriesId ? [['entities', seriesId]] : []),
]

export function useCheckConsistency(bookId: string) {
  return useApiMutation(
    (target: { nodeId?: string; actId?: string | null }) =>
      target.nodeId
        ? unwrap(
            api.POST('/api/nodes/{node_id}/consistency', {
              params: { path: { node_id: target.nodeId } },
            }),
          )
        : unwrap(
            api.POST('/api/books/{book_id}/consistency', {
              params: { path: { book_id: bookId } },
              body: { act_id: target.actId ?? null },
            }),
          ),
    () => [],
  )
}

export function useSuggest() {
  return useApiMutation(
    ({ actId, notes }: { actId: string; notes: string }) =>
      unwrap(
        api.POST('/api/acts/{act_id}/suggest', {
          params: { path: { act_id: actId } },
          body: { notes },
        }),
      ),
    () => [],
  )
}

export function useExtractLore(bookId: string) {
  return useApiMutation(
    (actId: string | null) =>
      unwrap(
        api.POST('/api/books/{book_id}/extract-lore', {
          params: { path: { book_id: bookId } },
          body: { act_id: actId },
        }),
      ),
    () => [],
  )
}

export function useSetAssistStatus(bookId: string) {
  return useApiMutation(
    ({ id, status }: { id: string; status: 'dismissed' | 'rejected' | 'open' }) =>
      unwrap(
        api.PATCH('/api/assist/{item_id}', { params: { path: { item_id: id } }, body: { status } }),
      ),
    () => touched(bookId),
  )
}

export function useAcceptSuggestion(bookId: string) {
  return useApiMutation(
    ({ id, nodes, choices }: { id: string; nodes?: string[]; choices?: number[] }) =>
      unwrap(
        api.POST('/api/assist/{item_id}/accept-suggestion', {
          params: { path: { item_id: id } },
          body: { nodes: nodes ?? [], choices: choices ?? [] },
        }),
      ),
    () => touched(bookId),
  )
}

export function useRejectSuggestion(bookId: string) {
  return useApiMutation(
    ({ id, nodes, choices }: { id: string; nodes?: string[]; choices?: number[] }) =>
      unwrap(
        api.POST('/api/assist/{item_id}/reject-suggestion', {
          params: { path: { item_id: id } },
          body: { nodes: nodes ?? [], choices: choices ?? [] },
        }),
      ),
    () => touched(bookId),
  )
}

export function useAcceptLore(bookId: string, seriesId: string) {
  return useApiMutation(
    ({ id, fields }: { id: string; fields?: Record<string, string> }) =>
      unwrap(
        api.POST('/api/assist/{item_id}/accept-lore', {
          params: { path: { item_id: id } },
          body: { fields },
        }),
      ),
    () => touched(bookId, seriesId),
  )
}
