import { screen } from '@testing-library/react'

import { mockHealth, renderApp } from '@/test/render'
import { useUiStore } from '@/stores/ui'

afterEach(() => vi.restoreAllMocks())

describe('CommandPalette', () => {
  it('opens with Ctrl+K and navigates to a section', async () => {
    mockHealth('ok')
    const { user, router } = renderApp('/story')
    await user.keyboard('{Control>}k{/Control}')
    const input = await screen.findByPlaceholderText('Type a command or search…')
    await user.type(input, 'lore')
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('heading', { name: 'Lore' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/lore')
    expect(screen.queryByPlaceholderText('Type a command or search…')).not.toBeInTheDocument()
  })

  it('opens from the top bar search button and sets the tier', async () => {
    mockHealth('ok')
    const { user } = renderApp('/story')
    await user.click(screen.getByRole('button', { name: /Search or run a command/ }))
    await user.type(screen.getByPlaceholderText('Type a command or search…'), 'medium')
    await user.keyboard('{Enter}')
    expect(useUiStore.getState().tier).toBe('medium')
  })

  it('closes with Escape', async () => {
    mockHealth('ok')
    const { user } = renderApp('/story')
    await user.keyboard('{Control>}k{/Control}')
    expect(await screen.findByPlaceholderText('Type a command or search…')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByPlaceholderText('Type a command or search…')).not.toBeInTheDocument()
  })
})
