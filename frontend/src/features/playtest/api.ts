import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { api, unwrap } from '@/api/client'
import type { components } from '@/api/schema'

type S = components['schemas']
export type PlayIn = S['PlayIn']
export type PlayOut = S['PlayOut']
export type PlayInput = NonNullable<PlayIn['inputs']>[number]
export type BatchIn = S['BatchIn']
export type BatchOut = S['BatchOut']
export type BatchDetail = S['BatchDetail']
export type JobOut = S['JobOut']
export type RunOut = S['RunOut']
export type BotName = S['BotOut']['name']

export const pk = {
  all: (bookId: string) => ['playtest', bookId] as const,
  play: (bookId: string, body: PlayIn) => ['playtest', bookId, 'play', body] as const,
  batches: (bookId: string) => ['playtest', bookId, 'batches'] as const,
  batch: (id: string) => ['playtest-batch', id] as const,
  runs: (id: string, outcome: string | null, offset: number) =>
    ['playtest-batch', id, 'runs', outcome, offset] as const,
  replay: (id: string, index: number, upto: number | null) =>
    ['playtest-batch', id, 'replay', index, upto] as const,
  job: (id: string) => ['job', id] as const,
}

/** Replays the reader's inputs server-side; the previous view stays up while it loads. */
export function usePlay(bookId: string, body: PlayIn | null) {
  return useQuery({
    queryKey: pk.play(bookId, body ?? { tier: '' }),
    queryFn: () =>
      unwrap(
        api.POST('/api/books/{book_id}/play', {
          params: { path: { book_id: bookId } },
          body: body!,
        }),
      ),
    enabled: !!body?.tier,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
    retry: false,
  })
}

export function useBots() {
  return useQuery({
    queryKey: ['playtest', 'bots'],
    queryFn: () => unwrap(api.GET('/api/playtest/bots')),
    staleTime: Infinity,
  })
}

export function useBatches(bookId: string) {
  return useQuery({
    queryKey: pk.batches(bookId),
    queryFn: () =>
      unwrap(api.GET('/api/books/{book_id}/batches', { params: { path: { book_id: bookId } } })),
    staleTime: 0,
  })
}

export function useBatch(id: string | null) {
  return useQuery({
    queryKey: pk.batch(id ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/batches/{batch_id}', { params: { path: { batch_id: id! } } })),
    enabled: !!id,
  })
}

export function useRuns(id: string, outcome: string | null, offset: number) {
  return useQuery({
    queryKey: pk.runs(id, outcome, offset),
    queryFn: () =>
      unwrap(
        api.GET('/api/batches/{batch_id}/runs', {
          params: { path: { batch_id: id }, query: { outcome, offset, limit: 25 } },
        }),
      ),
    placeholderData: keepPreviousData,
  })
}

export function useReplay(id: string, index: number, upto: number | null) {
  return useQuery({
    queryKey: pk.replay(id, index, upto),
    queryFn: () =>
      unwrap(
        api.GET('/api/batches/{batch_id}/runs/{index}/replay', {
          params: { path: { batch_id: id, index }, query: { upto } },
        }),
      ),
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  })
}

export function useCreateBatch(bookId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: BatchIn) =>
      unwrap(
        api.POST('/api/books/{book_id}/batches', { params: { path: { book_id: bookId } }, body }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: pk.batches(bookId) }),
  })
}

export function useResumeBatch(bookId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, budget }: { id: string; budget?: number | null }) =>
      unwrap(
        api.POST('/api/batches/{batch_id}/resume', {
          params: { path: { batch_id: id } },
          body: { budget_usd: budget ?? null },
        }),
      ),
    onSuccess: (b) => {
      void qc.invalidateQueries({ queryKey: pk.batches(bookId) })
      void qc.invalidateQueries({ queryKey: pk.batch(b.id) })
    },
  })
}

export function useDeleteBatch(bookId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(api.DELETE('/api/batches/{batch_id}', { params: { path: { batch_id: id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: pk.batches(bookId) }),
  })
}

export function useCancelJob() {
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(api.POST('/api/jobs/{job_id}/cancel', { params: { path: { job_id: id } } })),
  })
}

export function useStartCoverage(bookId: string) {
  return useMutation({
    mutationFn: (body: S['CoverageIn']) =>
      unwrap(
        api.POST('/api/books/{book_id}/coverage', { params: { path: { book_id: bookId } }, body }),
      ),
  })
}

export const isActive = (status: string | undefined) => status === 'queued' || status === 'running'

/**
 * Live job state over server-sent events. If the stream fails it falls back to
 * polling, so a job is never left looking "running". Calls `onDone` once when
 * the job leaves queued/running.
 */
export function useJobStream(jobId: string | null | undefined, onDone?: (job: JobOut) => void) {
  const [job, setJob] = useState<JobOut | null>(null)
  const done = useRef(onDone)
  useEffect(() => {
    done.current = onDone
  })
  useEffect(() => {
    if (!jobId) return
    let finished = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const update = (next: JobOut) => {
      setJob(next)
      if (!finished && !isActive(next.status)) {
        finished = true
        source.close()
        done.current?.(next)
      }
    }
    const poll = async () => {
      if (finished) return
      try {
        update(await unwrap(api.GET('/api/jobs/{job_id}', { params: { path: { job_id: jobId } } })))
      } catch {
        // keep trying: the server may be restarting
      }
      if (!finished) timer = setTimeout(() => void poll(), 1000)
    }
    const source = new EventSource(`/api/jobs/${jobId}/events`)
    source.onmessage = (e) => update(JSON.parse(e.data as string) as JobOut)
    source.onerror = () => {
      source.close()
      if (!finished && timer === undefined) void poll()
    }
    return () => {
      finished = true
      source.close()
      clearTimeout(timer)
    }
  }, [jobId])
  return job?.id === jobId ? job : null
}
