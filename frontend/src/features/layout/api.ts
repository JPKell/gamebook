import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef } from 'react'

import { api, ApiError, unwrap } from '@/api/client'
import type { components } from '@/api/schema'
import { artKeys, type PageSetup, usePageSetup } from '@/features/art/api'

import { asLayout, type Layout, layoutBody } from './model'

type S = components['schemas']
export type Fonts = S['FontsOut']

const fontsKey = ['print', 'fonts'] as const

export function useFonts() {
  return useQuery({
    queryKey: fontsKey,
    queryFn: () => unwrap(api.GET('/api/print/fonts')),
    staleTime: 60_000,
  })
}

export function useUploadFont() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) => {
      const res = await fetch('/api/print/fonts', {
        method: 'POST',
        body: file,
        headers: { 'Content-Type': 'application/octet-stream' },
      })
      const body = (await res.json().catch(() => ({}))) as { detail?: string; code?: string }
      if (!res.ok)
        throw new ApiError(
          res.status,
          body.code ?? `http_${res.status}`,
          body.detail ?? res.statusText,
        )
      return body as unknown as S['FontOut']
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: fontsKey }),
  })
}

export function useDeleteFont() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(api.DELETE('/api/print/fonts/{font_id}', { params: { path: { font_id: id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: fontsKey }),
  })
}

export const sampleUrl = (bookId: string, tier: string | null, imposed: boolean) => {
  const q = new URLSearchParams()
  if (tier) q.set('tier', tier)
  if (imposed) q.set('imposed', 'true')
  return `/api/books/${bookId}/print/sample?${q}`
}

/**
 * The book's layout with optimistic edits. Each edit applies to the latest value
 * (not the last render's), so quick changes don't overwrite each other; saves run
 * in order and the server's answer (which may adjust the page size) wins.
 */
export function useLayout(bookId: string) {
  const qc = useQueryClient()
  const setup = usePageSetup(bookId)
  const key = artKeys.setup(bookId)
  const queue = useRef(Promise.resolve())
  const pending = useRef(0)
  const save = useMutation({
    mutationFn: (body: S['PageSetup']) => {
      const run = queue.current.then(() =>
        unwrap(
          api.PUT('/api/books/{book_id}/page-setup', {
            params: { path: { book_id: bookId } },
            body,
          }),
        ),
      )
      queue.current = run.then(
        () => undefined,
        () => undefined,
      )
      return run
    },
    // Only the last edit's answer: earlier ones would undo edits still on their way.
    // (Edits count from the moment they are made, not when their request starts.)
    onSuccess: (data) => {
      pending.current -= 1
      if (pending.current === 0) qc.setQueryData(key, data)
    },
    // Back to the server's value, once nothing else is on its way.
    onError: () => {
      pending.current -= 1
      if (pending.current === 0) void qc.invalidateQueries({ queryKey: key })
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['book', bookId, 'print'] }),
  })
  const layout = setup.data ? asLayout(setup.data) : null
  const update = (fn: (l: Layout) => Layout) => {
    // A refetch in flight would land on top of this edit: cancel it, keeping the data
    // as it is (the default would restore what it started from, after the edit).
    void qc.cancelQueries({ queryKey: key }, { revert: false })
    const current = qc.getQueryData<PageSetup>(key)
    if (!current) return
    const next = fn(asLayout(current))
    qc.setQueryData(key, { ...current, ...next })
    pending.current += 1
    save.mutate(layoutBody(next))
  }
  return { layout, update, save, isPending: setup.isPending, error: setup.error }
}
