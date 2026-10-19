import { screen, waitFor, within } from '@testing-library/react'

import { mockHealth, renderApp } from '@/test/render'
import { useUiStore } from '@/stores/ui'

import { SECTIONS } from './sections'

afterEach(() => vi.restoreAllMocks())

describe('AppShell', () => {
  it('redirects / to the Story section, which points to the Library when no book is open', async () => {
    mockHealth('ok')
    const { router } = renderApp('/')
    expect(
      await screen.findByRole('heading', { name: 'Open a book to start writing' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/story')
    expect(screen.getByRole('link', { name: 'Go to the Library' })).toHaveAttribute(
      'href',
      '/library',
    )
  })

  it('reopens the last book from /story', async () => {
    mockHealth('ok')
    useUiStore.setState({ lastBookId: 'b1' })
    const { router } = renderApp('/story', { keepUi: true })
    await waitFor(() => expect(router.state.location.pathname).toBe('/story/b1'))
  })

  it('renders a nav link for every section and navigates', async () => {
    mockHealth('ok')
    const { user, router } = renderApp('/story')
    const nav = screen.getByRole('navigation', { name: 'Primary' })
    for (const s of SECTIONS) {
      expect(within(nav).getByRole('link', { name: s.label })).toBeInTheDocument()
    }
    await user.click(within(nav).getByRole('link', { name: 'Export' }))
    expect(await screen.findByRole('heading', { name: 'Export' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/export')
    expect(within(nav).getByRole('link', { name: 'Export' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('shows backend connected status', async () => {
    mockHealth('ok')
    renderApp('/story')
    expect(await screen.findByText('Connected · v9.9.9')).toBeInTheDocument()
  })

  it('shows backend unreachable status', async () => {
    mockHealth('down')
    renderApp('/story')
    expect(await screen.findByText('Backend unreachable')).toBeInTheDocument()
  })

  it('renders not found for unknown routes', async () => {
    mockHealth('ok')
    renderApp('/nope')
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })
})

describe('tier selector', () => {
  it('switches the active rules tier', async () => {
    mockHealth('ok')
    const { user } = renderApp('/story')
    const group = screen.getByRole('radiogroup', { name: 'Rules tier' })
    expect(within(group).getByRole('radio', { name: 'Basic' })).toBeChecked()
    await user.click(within(group).getByRole('radio', { name: 'Advanced' }))
    expect(within(group).getByRole('radio', { name: 'Advanced' })).toBeChecked()
    expect(useUiStore.getState().tier).toBe('advanced')
  })
})

describe('problems panel', () => {
  it('toggles with the status bar button and Ctrl+J', async () => {
    mockHealth('ok')
    const { user } = renderApp('/story')
    expect(screen.queryByRole('region', { name: 'Problems' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { expanded: false }))
    expect(screen.getByRole('region', { name: 'Problems' })).toBeInTheDocument()
    await user.keyboard('{Control>}j{/Control}')
    expect(screen.queryByRole('region', { name: 'Problems' })).not.toBeInTheDocument()
  })
})

describe('theme', () => {
  it('cycles system → light → dark and applies the class', async () => {
    mockHealth('ok')
    const { user } = renderApp('/story')
    await user.click(screen.getByRole('button', { name: /System theme/ }))
    expect(document.documentElement).not.toHaveClass('dark')
    await user.click(screen.getByRole('button', { name: /Light theme/ }))
    await waitFor(() => expect(document.documentElement).toHaveClass('dark'))
  })
})
