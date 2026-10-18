import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from '@/api/client'
import { useApiMutation } from '@/api/queries'
import type { components } from '@/api/schema'

type S = components['schemas']
export type QueueRow = S['QueueRow']
export type ProseOut = S['ProseOut']
export type VariantProse = S['VariantProse']
export type PipelineRun = S['PipelineRunOut']
export type ProseStatus = QueueRow['status']

export const wk = {
  all: ['writing'] as const,
  // Under ['book', id] so story edits (beat notes, choices, lore links) refresh them.
  queue: (bookId: string) => ['book', bookId, 'writing-queue'] as const,
  node: (bookId: string, nodeId: string) => ['book', bookId, 'prose', nodeId] as const,
  context: (bookId: string, variantId: string) =>
    ['book', bookId, 'writing-context', variantId] as const,
  run: (id: string) => ['writing', 'run', id] as const,
}

/** Writing edits change queue status, problems (stale prose) and the player's text. */
const affected = (bookId: string) => [wk.all, ['book', bookId], ['playtest']]

export function useQueue(bookId: string) {
  return useQuery({
    queryKey: wk.queue(bookId),
    queryFn: () =>
      unwrap(
        api.GET('/api/books/{book_id}/writing-queue', { params: { path: { book_id: bookId } } }),
      ),
    staleTime: 0,
  })
}

export function useNodeProse(bookId: string, nodeId: string | undefined) {
  return useQuery({
    queryKey: wk.node(bookId, nodeId ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/nodes/{node_id}/prose', { params: { path: { node_id: nodeId! } } })),
    enabled: !!nodeId,
    staleTime: 0,
  })
}

export function useContext(bookId: string, variantId: string | undefined) {
  return useQuery({
    queryKey: wk.context(bookId, variantId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/variants/{variant_id}/context', {
          params: { path: { variant_id: variantId! } },
        }),
      ),
    enabled: !!variantId,
    staleTime: 0,
  })
}

export function usePipelineRun(id: string | null | undefined) {
  return useQuery({
    queryKey: wk.run(id ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/pipeline-runs/{run_id}', { params: { path: { run_id: id! } } })),
    enabled: !!id,
  })
}

export function useGenerate(bookId: string) {
  return useApiMutation(
    ({ variantId, notes }: { variantId: string; notes: string }) =>
      unwrap(
        api.POST('/api/variants/{variant_id}/generate', {
          params: { path: { variant_id: variantId } },
          body: { notes },
        }),
      ),
    () => affected(bookId),
  )
}

export function useGenerateAct(bookId: string) {
  return useApiMutation(
    ({
      actId,
      only,
      max_cost_usd,
    }: {
      actId: string
      only: 'missing' | 'stale' | 'all'
      max_cost_usd: number | null
    }) =>
      unwrap(
        api.POST('/api/acts/{act_id}/generate', {
          params: { path: { act_id: actId } },
          body: { only, max_cost_usd },
        }),
      ),
    () => affected(bookId),
  )
}

export function useApprove(bookId: string) {
  return useApiMutation(
    ({ id, text, summary }: { id: string; text?: string; summary?: string }) =>
      unwrap(
        api.POST('/api/prose/{prose_id}/approve', {
          params: { path: { prose_id: id } },
          body: { text, summary },
        }),
      ),
    () => affected(bookId),
  )
}

export function useReject(bookId: string) {
  return useApiMutation(
    ({ id, notes }: { id: string; notes: string }) =>
      unwrap(
        api.POST('/api/prose/{prose_id}/reject', {
          params: { path: { prose_id: id } },
          body: { notes },
        }),
      ),
    () => affected(bookId),
  )
}

export function useWriteProse(bookId: string) {
  return useApiMutation(
    ({ variantId, text, approve }: { variantId: string; text: string; approve: boolean }) =>
      unwrap(
        api.POST('/api/variants/{variant_id}/prose', {
          params: { path: { variant_id: variantId } },
          body: { text, approve },
        }),
      ),
    () => affected(bookId),
  )
}

export function useSaveSummary(bookId: string) {
  return useApiMutation(
    ({ id, summary }: { id: string; summary: string }) =>
      unwrap(
        api.PUT('/api/prose/{prose_id}/summary', {
          params: { path: { prose_id: id } },
          body: { summary },
        }),
      ),
    () => affected(bookId),
  )
}

export const STATUS_LABELS: Record<ProseStatus, string> = {
  none: 'Not written',
  draft: 'Draft',
  in_review: 'In review',
  approved: 'Approved',
  stale: 'Stale',
}

export const STATUS_TONE: Record<ProseStatus, string> = {
  none: 'bg-surface-2 text-muted',
  draft: 'bg-surface-2 text-text',
  in_review: 'bg-accent/12 text-accent',
  approved: 'bg-success/12 text-success',
  stale: 'bg-warning/15 text-warning',
}
