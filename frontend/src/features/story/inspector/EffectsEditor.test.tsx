import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { CurrencyQuick } from './EffectsEditor'
import type { EffectIn } from './effects'

const GOLD = { key: 'GOLD', label: 'Gold' }

function setup(effects: EffectIn[], defaultOnce = true) {
  const onChange = vi.fn()
  render(
    <CurrencyQuick
      effects={effects}
      onChange={onChange}
      currency={GOLD}
      defaultOnce={defaultOnce}
    />,
  )
  return onChange
}

describe('CurrencyQuick', () => {
  it('adds a money effect, first time only on arrival', async () => {
    const user = userEvent.setup()
    const flag = { op: 'set_flag', flag: 'SEEN' } as EffectIn
    const onChange = setup([flag])
    await user.type(screen.getByLabelText('Gold gained or lost'), '5{Enter}')
    expect(onChange).toHaveBeenCalledWith([
      { op: 'modify', stat: 'GOLD', amount: '5', once: true },
      flag,
    ])
  })

  it('repeats on choices', async () => {
    const user = userEvent.setup()
    const onChange = setup([], false)
    await user.type(screen.getByLabelText('Gold gained or lost'), '-3{Enter}')
    expect(onChange).toHaveBeenCalledWith([
      { op: 'modify', stat: 'GOLD', amount: '-3', once: false },
    ])
  })

  it('edits and removes the existing money effect', async () => {
    const user = userEvent.setup()
    const gold = { op: 'modify', stat: 'GOLD', amount: '4', once: true } as EffectIn
    const other = { op: 'modify', stat: 'STAMINA', amount: '-2' } as EffectIn
    const onChange = setup([other, gold])
    const input = screen.getByLabelText('Gold gained or lost')
    expect(input).toHaveValue(4)
    await user.clear(input)
    await user.type(input, '7{Enter}')
    expect(onChange).toHaveBeenLastCalledWith([other, { ...gold, amount: '7' }])
    await user.clear(input)
    await user.tab()
    expect(onChange).toHaveBeenLastCalledWith([other])
  })

  it('leaves formulas to the full editor', () => {
    setup([{ op: 'modify', stat: 'GOLD', amount: '1d6' } as EffectIn])
    expect(screen.queryByLabelText('Gold gained or lost')).toBeNull()
    expect(screen.getByText('1d6')).toBeInTheDocument()
  })
})
