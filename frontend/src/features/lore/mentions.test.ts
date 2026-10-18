import { describe, expect, it } from 'vitest'

import { type MentionTarget, segments } from './mentions'

const targets: MentionTarget[] = [
  { kind: 'character', id: 'c1', key: 'mara', name: 'Mara' },
  { kind: 'lore', id: 'l1', key: 'mara', name: 'Mara (the river)' },
  { kind: 'lore', id: 'l2', key: 'crypt', name: 'The Crypt' },
]

describe('segments', () => {
  it('resolves mentions, labels and explicit kinds', () => {
    const s = segments('Ask [[mara]] about [[lore:mara|the river]] near [[crypt]].', targets)
    expect(s).toEqual([
      { text: 'Ask ' },
      { mention: '[[mara]]', label: 'Mara', target: targets[0] },
      { text: ' about ' },
      { mention: '[[lore:mara|the river]]', label: 'the river', target: targets[1] },
      { text: ' near ' },
      { mention: '[[crypt]]', label: 'The Crypt', target: targets[2] },
      { text: '.' },
    ])
  })

  it('keeps unknown mentions as broken links', () => {
    expect(segments('[[ghost]]', targets)).toEqual([
      { mention: '[[ghost]]', label: 'ghost', target: null },
    ])
    expect(segments('[[character:crypt]]', targets)[0]).toMatchObject({ target: null })
  })
})
