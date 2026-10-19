import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useLatest } from './useLatest'

describe('useLatest', () => {
  it('merges quick edits instead of each starting from the stale server copy', () => {
    const server = { size: 'half', align: 'center' }
    const { result, rerender } = renderHook(({ s, pending }) => useLatest(s, pending), {
      initialProps: { s: server, pending: false },
    })
    expect(result.current({ size: 'full_width' })).toEqual({ size: 'full_width', align: 'center' })
    rerender({ s: server, pending: true }) // first save in flight; server copy not updated yet
    expect(result.current({ align: 'left' })).toEqual({ size: 'full_width', align: 'left' })
  })

  it('follows the server again once nothing is in flight', () => {
    const { result, rerender } = renderHook(({ s, pending }) => useLatest(s, pending), {
      initialProps: { s: { a: 1, b: 1 }, pending: false },
    })
    result.current({ a: 2 })
    rerender({ s: { a: 5, b: 5 }, pending: false }) // changed elsewhere (e.g. undo)
    expect(result.current({ b: 6 })).toEqual({ a: 5, b: 6 })
  })
})
