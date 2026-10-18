import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { mockApi } from '@/test/render'

import { useJobStream } from './api'

/** EventSource stand-in whose stream fails straight away (proxy hiccup, server restart). */
class FailingSource {
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  constructor() {
    setTimeout(() => this.onerror?.(), 0)
  }
  close() {
    this.closed = true
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it('falls back to polling when the event stream fails (review regression)', async () => {
  vi.stubGlobal('EventSource', FailingSource)
  const job = {
    id: 'j1',
    kind: 'batch',
    status: 'done',
    progress: 10,
    total: 10,
    label: '',
    error: null,
    result: null,
    created_at: 'x',
    started_at: null,
    finished_at: null,
  }
  mockApi({ 'GET /api/jobs/j1': job })
  const onDone = vi.fn()
  const { result } = renderHook(() => useJobStream('j1', onDone))
  await waitFor(() => expect(result.current?.status).toBe('done'))
  expect(onDone).toHaveBeenCalledTimes(1)
})
