import { screen, waitFor, within } from '@testing-library/react'

import { mockApi, renderApp } from '@/test/render'

afterEach(() => vi.restoreAllMocks())

const series = {
  id: 's1',
  key: 'ash',
  title: 'The Ashen Cycle',
  description: 'Grey.',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('LibraryPage', () => {
  it('lists series with their books and opens a book', async () => {
    mockApi({
      'GET /api/health': { status: 'ok', version: '1', database: 'ok' },
      'GET /api/series': [series],
      'GET /api/series/s1': {
        ...series,
        style: {},
        created_at: series.updated_at,
        books: [{ id: 'b1', key: 'b', number: 1, title: 'The Haunted Bridge' }],
      },
    })
    const { user, router } = renderApp('/library')
    const card = await screen.findByRole('region', { name: 'The Ashen Cycle' })
    await user.click(await within(card).findByRole('button', { name: 'The Haunted Bridge' }))
    expect(router.state.location.pathname).toBe('/story/b1')
  })

  it('creates a series from the empty state', async () => {
    const calls = mockApi({
      'GET /api/health': { status: 'ok', version: '1', database: 'ok' },
      'GET /api/series': [],
      'POST /api/series': ({ body }: { body: unknown }) => ({
        ...series,
        ...(body as object),
        style: {},
        created_at: '',
        books: [],
      }),
    })
    const { user } = renderApp('/library')
    await user.click(await screen.findByRole('button', { name: /Create your first series/ }))
    await user.type(screen.getByLabelText('Series title'), 'The Ashen Cycle')
    await user.click(screen.getByRole('button', { name: 'Create series' }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
        title: 'The Ashen Cycle',
        description: '',
      }),
    )
  })
})
