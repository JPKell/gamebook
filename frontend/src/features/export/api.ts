import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from '@/api/client'
import type { components } from '@/api/schema'

type S = components['schemas']
export type Preflight = S['PreflightOut']
export type VerifyOut = S['VerifyOut']

export const ek = {
  preflight: (bookId: string, tier: string | null) => ['book', bookId, 'print', tier] as const,
}

export function usePreflight(bookId: string, tier: string | null) {
  return useQuery({
    queryKey: ek.preflight(bookId, tier),
    queryFn: () =>
      unwrap(
        api.GET('/api/books/{book_id}/print/preflight', {
          params: { path: { book_id: bookId }, query: { tier } },
        }),
      ),
    retry: false,
  })
}

export function useReshuffle(bookId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (seed: number | null) =>
      unwrap(
        api.POST('/api/books/{book_id}/print/reshuffle', {
          params: { path: { book_id: bookId } },
          body: { seed },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['book', bookId, 'print'] }),
  })
}

export function useVerify(bookId: string) {
  return useMutation({
    mutationFn: (body: { tier: string | null; runs: number }) =>
      unwrap(
        api.POST('/api/books/{book_id}/print/verify', {
          params: { path: { book_id: bookId } },
          body,
        }),
      ),
  })
}

export function useStartExport(bookId: string) {
  return useMutation({
    mutationFn: (body: {
      tier: string | null
      format: 'pdf' | 'epub' | 'web'
      imposed?: boolean
    }) =>
      unwrap(
        api.POST('/api/books/{book_id}/print/exports', {
          params: { path: { book_id: bookId } },
          body,
        }),
      ),
  })
}

export const previewUrl = (bookId: string, tier: string | null) =>
  `/api/books/${bookId}/print/preview${tier ? `?tier=${encodeURIComponent(tier)}` : ''}`
export const downloadUrl = (jobId: string) => `/api/print/exports/${jobId}`
