import createClient from 'openapi-fetch'

import type { components, paths } from './schema'

export type Schemas = components['schemas']

/** Typed client generated from the backend's OpenAPI schema (`npm run gen:api`). */
export const api = createClient<paths>({
  baseUrl: globalThis.location?.origin ?? '',
  // Late-bound so tests can stub globalThis.fetch after import.
  fetch: (request) => globalThis.fetch(request),
})

/** Error raised for non-2xx responses; mirrors the backend error envelope. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

interface FetchResult<T> {
  data?: T
  error?: unknown
  response: Response
}

/** Await an openapi-fetch call, returning data or throwing ApiError. */
export async function unwrap<T>(call: Promise<FetchResult<T>>): Promise<T> {
  const { data, error, response } = await call
  if (error !== undefined || !response.ok) {
    const body = (error ?? {}) as { detail?: unknown; code?: unknown }
    throw new ApiError(
      response.status,
      typeof body.code === 'string' ? body.code : `http_${response.status}`,
      typeof body.detail === 'string' ? body.detail : response.statusText,
    )
  }
  return data as T
}
