import { api, ApiError, unwrap } from './client'

afterEach(() => vi.restoreAllMocks())

function respond(status: number, body: unknown) {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

describe('unwrap', () => {
  it('returns data on success', async () => {
    respond(200, { status: 'ok', version: '1', database: 'ok' })
    await expect(unwrap(api.GET('/api/health'))).resolves.toEqual({
      status: 'ok',
      version: '1',
      database: 'ok',
    })
  })

  it('throws ApiError with the backend envelope', async () => {
    respond(404, { detail: 'Book x not found', code: 'not_found' })
    const err = await unwrap(api.GET('/api/health')).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 404, code: 'not_found', message: 'Book x not found' })
  })

  it('falls back when the error body is not the envelope', async () => {
    respond(502, { oops: true })
    const err = await unwrap(api.GET('/api/health')).catch((e: unknown) => e)
    expect(err).toMatchObject({ status: 502, code: 'http_502' })
  })
})

describe('refresh after a write', () => {
  it('refetches even when the first load is still in flight', async () => {
    const { QueryClient, QueryObserver } = await import('@tanstack/react-query')
    const { refresh } = await import('./queries')
    const { waitFor } = await import('@testing-library/react')
    const qc = new QueryClient()
    let release!: (v: string[]) => void
    let calls = 0
    const queryFn = () => {
      calls++
      // The first request was sent before the write and answers late with old data.
      return calls === 1 ? new Promise<string[]>((r) => (release = r)) : Promise.resolve(['new'])
    }
    const observer = new QueryObserver(qc, { queryKey: ['list'], queryFn })
    const unsubscribe = observer.subscribe(() => {})
    await waitFor(() => expect(calls).toBe(1))
    await refresh(qc, [['list']])
    release(['stale'])
    await waitFor(() => expect(observer.getCurrentResult().data).toEqual(['new']))
    expect(calls).toBe(2)
    unsubscribe()
  })
})
