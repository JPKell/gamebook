import { QueryClient } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { Providers } from '@/app/providers'
import { routes } from '@/app/routes'
import { useUiStore } from '@/stores/ui'

const initialUi = useUiStore.getState()

/** Render the full app at a URL with a fresh query client and UI store. */
export function renderApp(url = '/') {
  useUiStore.setState(initialUi, true)
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
