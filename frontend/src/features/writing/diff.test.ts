import { describe, expect, it } from 'vitest'

import { diffWords } from './diff'

describe('diffWords', () => {
  it('marks added and removed words', () => {
    expect(diffWords('The raven lands on the gate.', 'The crow lands on the old gate.')).toEqual([
      { op: 'eq', text: 'The ' },
      { op: 'del', text: 'raven' },
      { op: 'add', text: 'crow' },
      { op: 'eq', text: ' lands on the ' },
      { op: 'add', text: 'old ' },
      { op: 'eq', text: 'gate.' },
    ])
  })

  it('reconstructs both texts', () => {
    const a = 'One two three.\n\nFour five.'
    const b = 'One three.\n\nFour five six.'
    const d = diffWords(a, b)
    expect(
      d
        .filter((p) => p.op !== 'add')
        .map((p) => p.text)
        .join(''),
    ).toBe(a)
    expect(
      d
        .filter((p) => p.op !== 'del')
        .map((p) => p.text)
        .join(''),
    ).toBe(b)
  })

  it('handles empty sides', () => {
    expect(diffWords('', 'New text')).toEqual([{ op: 'add', text: 'New text' }])
    expect(diffWords('Old', '')).toEqual([{ op: 'del', text: 'Old' }])
  })
})
