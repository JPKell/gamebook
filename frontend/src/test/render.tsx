import { QueryClient } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { Providers } from '@/app/providers'
import { routes } from '@/app/routes'
import { useUiStore } from '@/stores/ui'

const initialUi = useUiStore.getState()

/** Render the full app at a URL with a fresh query client and UI store. */
export function renderApp(url = '/', opts: { keepUi?: boolean } = {}) {
  if (!opts.keepUi) useUiStore.setState(initialUi, true)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(routes, { initialEntries: [url] })
  const user = userEvent.setup()
  const utils = render(
    <Providers client={client}>
      <RouterProvider router={router} />
    </Providers>,
  )
  return { ...utils, router, user }
}

export function mockHealth(response: 'ok' | 'down') {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
    if (response === 'down') throw new TypeError('Failed to fetch')
    return new Response(JSON.stringify({ status: 'ok', version: '9.9.9', database: 'ok' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
}

type Handler = (req: { method: string; path: string; body: unknown }) => unknown

/**
 * Route fetch calls by "METHOD /path" (path without the origin, query ignored).
 * Unmatched requests 404. Returns the list of calls for assertions.
 */
export function mockApi(routes: Record<string, unknown | Handler>) {
  const calls: { method: string; path: string; body: unknown }[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
    const req = input instanceof Request ? input : new Request(String(input))
    const path = new URL(req.url).pathname
    const text = await req.text()
    const body = text ? JSON.parse(text) : undefined
    calls.push({ method: req.method, path, body })
    const route = routes[`${req.method} ${path}`]
    if (route === undefined)
      return new Response(JSON.stringify({ detail: 'Not Found', code: 'not_found' }), {
        status: 404,
      })
    const data =
      typeof route === 'function' ? (route as Handler)({ method: req.method, path, body }) : route
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  return calls
}
