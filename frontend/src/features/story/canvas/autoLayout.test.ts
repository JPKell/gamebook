import { act, choice, graph, node } from '@/test/fixtures'

import { autoLayout } from './autoLayout'
import { NODE_WIDTH } from './flow'

describe('autoLayout', () => {
  it('lays acts out left to right and flows each act rightwards', async () => {
    const g = graph(
      [
        node('a', 'a1', 0, 0, { choices: [choice('c1', 'a', 'b'), choice('c2', 'a', 'c')] }),
        node('b', 'a1', 0, 0, { choices: [choice('c3', 'b', 'd')] }),
        node('c', 'a1', 0, 0),
        node('d', 'a2', 0, 0),
      ],
      [act('a1', 0), act('a2', 1)],
    )
    const pos = new Map((await autoLayout(g, new Map())).map((p) => [p.id, p]))
    expect(pos.size).toBe(4)
    expect(pos.get('b')!.x).toBeGreaterThan(pos.get('a')!.x)
    expect(pos.get('c')!.x).toBeGreaterThan(pos.get('a')!.x)
    expect(pos.get('d')!.x).toBeGreaterThan(Math.max(pos.get('b')!.x, pos.get('c')!.x) + NODE_WIDTH)
    // Siblings don't overlap.
    expect(Math.abs(pos.get('b')!.y - pos.get('c')!.y)).toBeGreaterThan(50)
  })
})
