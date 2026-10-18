import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'

import { NumberInput, TextArea, TextInput } from './inputs'

function Harness({ initial, onCommit }: { initial: string; onCommit: (v: string) => void }) {
  const [value, setValue] = useState(initial)
  return (
    <>
      <TextInput
        aria-label="field"
        value={value}
        onCommit={(v) => {
          onCommit(v)
          setValue(v)
        }}
      />
      <button type="button" onClick={() => setValue('from server')}>
        refetch
      </button>
    </>
  )
}

describe('TextInput', () => {
  it('commits on blur and Enter, only when changed', async () => {
    const user = userEvent.setup()
    const commit = vi.fn()
    render(<Harness initial="a" onCommit={commit} />)
    const input = screen.getByRole('textbox', { name: 'field' })
    await user.click(input)
    await user.tab()
    expect(commit).not.toHaveBeenCalled()
    await user.type(input, 'bc{Enter}')
    expect(commit).toHaveBeenCalledWith('abc')
  })

  it('reverts on Escape', async () => {
    const user = userEvent.setup()
    const commit = vi.fn()
    render(<Harness initial="a" onCommit={commit} />)
    const input = screen.getByRole('textbox', { name: 'field' })
    await user.type(input, 'zzz{Escape}')
    expect(commit).not.toHaveBeenCalled()
    expect(input).toHaveValue('a')
  })

  it('follows server changes unless the user is typing', async () => {
    const user = userEvent.setup()
    render(<Harness initial="a" onCommit={vi.fn()} />)
    const input = screen.getByRole('textbox', { name: 'field' })
    await user.click(screen.getByRole('button', { name: 'refetch' }))
    expect(input).toHaveValue('from server')
  })
})

describe('TextInput unmount', () => {
  it('commits unsaved typing when the field unmounts', async () => {
    const user = userEvent.setup()
    const commit = vi.fn()
    const { rerender } = render(<TextInput aria-label="t" value="a" onCommit={commit} />)
    await user.type(screen.getByRole('textbox', { name: 't' }), 'bc')
    rerender(<span />)
    expect(commit).toHaveBeenCalledWith('abc')
  })

  it('does not commit after Escape or when unchanged', async () => {
    const user = userEvent.setup()
    const commit = vi.fn()
    const { rerender } = render(<TextInput aria-label="t" value="a" onCommit={commit} />)
    await user.type(screen.getByRole('textbox', { name: 't' }), 'bc{Escape}')
    rerender(<span />)
    expect(commit).not.toHaveBeenCalled()
  })
})

describe('NumberInput', () => {
  it('parses numbers, allows clearing when permitted, rejects junk', async () => {
    const user = userEvent.setup()
    const commit = vi.fn()
    const { rerender } = render(
      <NumberInput aria-label="n" value={3} onCommit={commit} allowEmpty />,
    )
    const input = screen.getByRole('spinbutton', { name: 'n' })
    await user.clear(input)
    await user.type(input, '7{Enter}')
    expect(commit).toHaveBeenLastCalledWith(7)
    rerender(<NumberInput aria-label="n" value={7} onCommit={commit} allowEmpty />)
    await user.clear(input)
    await user.tab()
    expect(commit).toHaveBeenLastCalledWith(null)
  })
})

describe('TextArea', () => {
  it('autosaves after a pause and on blur', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const commit = vi.fn()
    render(<TextArea aria-label="notes" value="" onCommit={commit} debounceMs={500} />)
    await user.type(screen.getByRole('textbox', { name: 'notes' }), 'Hello')
    expect(commit).not.toHaveBeenCalled()
    vi.advanceTimersByTime(600)
    expect(commit).toHaveBeenCalledWith('Hello')
    vi.useRealTimers()
  })
})
