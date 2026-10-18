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
