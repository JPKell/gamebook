import { act, choice, graph, node } from '@/test/fixtures'

import { NO_FILTERS } from '../storyStore'
import { matchesFilters, matchesSearch, nodeOptions, problemsByNode } from '../model'
import {
  FRAME_HEADER,
  FRAME_PADDING,
  NODE_WIDTH,
  actAt,
  buildEdges,
  buildNodes,
  computeFrames,
  outcomeLabel,
} from './flow'

const all = () => true

describe('buildEdges', () => {
  it('creates one edge per targeted outcome with readable labels', () => {
    const roll = choice('c2', 'a', null, {
      label: 'Gamble',
      kind: 'roll',
      outcomes: [
        { id: 'o1', position: 0, key: 'low', target_node_id: 'b', range_lo: 2, range_hi: 6 },
        { id: 'o2', position: 1, key: 'high', target_node_id: 'c', range_lo: 7, range_hi: 12 },
      ],
    })
    const g = graph(
      [
        node('a', 'a1', 0, 0, {
          choices: [
            choice('c1', 'a', 'b', { label: 'Go', condition: 'has(rope)' }),
            roll,
            choice('c3', 'a', null),
          ],
        }),
        node('b', 'a1', 300, 0),
        node('c', 'a2', 600, 0),
      ],
      [act('a1', 0), act('a2', 1)],
    )
    const edges = buildEdges(g, all)
    expect(edges.map((e) => [e.id, e.source, e.target, e.data?.label, e.data?.crossAct])).toEqual([
      ['c1:default', 'a', 'b', 'Go', false],
      ['c2:low', 'a', 'b', 'Gamble · 2–6', false],
      ['c2:high', 'a', 'c', 'Gamble · 7–12', true],
    ])
  })

  it('labels combat/test outcomes by key and blank goto choices clearly', () => {
    const fight = choice('c', 'a', 'b', { label: 'Fight', kind: 'combat' })
    expect(
      outcomeLabel({ ...fight, outcomes: [{ ...fight.outcomes[0]!, key: 'win' }] }, 'win'),
    ).toBe('Fight · win')
    expect(outcomeLabel(choice('c', 'a', 'b', { label: ' ' }), 'default')).toBe('(no text)')
  })
})

describe('buildNodes', () => {
  it('marks the start node, colours by act and dims hidden nodes', () => {
    const g = graph([node('a', 'a1', 0, 0), node('b', 'a1', 10, 10)])
    const nodes = buildNodes(g, new Map(), (n) => n.id === 'a')
    expect(nodes.map((n) => [n.id, n.data.isStart, n.data.dimmed])).toEqual([
      ['a', true, false],
      ['b', false, true],
    ])
    expect(nodes[0]!.data.actColor).toMatch(/^#/)
  })
})

describe('computeFrames', () => {
  it('wraps each act around its nodes', () => {
    const g = graph(
      [node('a', 'a1', 0, 0), node('b', 'a1', 400, 200)],
      [act('a1', 0), act('a2', 1)],
    )
    const nodes = buildNodes(g, new Map(), all).map((n) => ({
      ...n,
      measured: { width: NODE_WIDTH, height: 100 },
    }))
    const [f1, f2] = computeFrames(g, nodes)
    expect(f1!.position).toEqual({ x: -FRAME_PADDING, y: -FRAME_PADDING - FRAME_HEADER })
    expect(f1!.width).toBe(400 + NODE_WIDTH + 2 * FRAME_PADDING)
    expect(f1!.height).toBe(300 + 2 * FRAME_PADDING + FRAME_HEADER)
    expect(f1!.data.count).toBe(2)
    // Empty acts get a placeholder frame to the right, so they can still receive nodes.
    expect(f2!.data.count).toBe(0)
    expect(f2!.position.x).toBeGreaterThan(400 + NODE_WIDTH)
  })

  it('finds the act at a point, preferring the smallest frame', () => {
    const g = graph(
      [node('a', 'a1', 0, 0), node('a2n', 'a1', 600, 300), node('b', 'a2', 50, 50)],
      [act('a1', 0), act('a2', 1)],
    )
    const frames = computeFrames(g, buildNodes(g, new Map(), all))
    expect(actAt(frames, 60, 60)).toBe('a2')
    expect(actAt(frames, -10, -10)).toBe('a1')
    expect(actAt(frames, 5000, 5000)).toBeNull()
  })
})

describe('model helpers', () => {
  const n = node('hall', 'a1', 0, 0, {
    title: 'Hall of Echoes',
    beat_notes: 'A ghost waits.',
    encounters: [
      {
        id: 'e',
        position: 0,
        label: '',
        mode: 'fixed',
        fight: 'sequential',
        table_id: null,
        enemies: [],
      },
    ],
  })

  it('searches title, key and notes case-insensitively', () => {
    expect(matchesSearch(n, 'ECHO')).toBe(true)
    expect(matchesSearch(n, 'ghost')).toBe(true)
    expect(matchesSearch(n, 'hall_')).toBe(false)
    expect(matchesSearch(n, '  ')).toBe(true)
  })

  it('filters by node features and problems', () => {
    const problems = problemsByNode([
      {
        severity: 'error',
        code: 'x',
        message: 'bad',
        node_id: 'hall',
        act_id: null,
        choice_id: null,
        entity_type: null,
        entity_id: null,
        field: null,
      },
      {
        severity: 'warning',
        code: 'y',
        message: 'meh',
        node_id: 'hall',
        act_id: null,
        choice_id: null,
        entity_type: null,
        entity_id: null,
        field: null,
      },
    ])
    expect(problems.get('hall')).toEqual({ errors: 1, warnings: 1, messages: ['bad', 'meh'] })
    expect(matchesFilters(n, { ...NO_FILTERS, encounters: true }, problems)).toBe(true)
    expect(matchesFilters(n, { ...NO_FILTERS, endings: true }, problems)).toBe(false)
    expect(matchesFilters(n, { ...NO_FILTERS, problems: true }, new Map())).toBe(false)
  })

  it('groups node options by act in act order', () => {
    const g = graph(
      [node('z', 'a2', 0, 0), node('b', 'a1', 0, 0), node('a', 'a1', 0, 0)],
      [act('a1', 0), act('a2', 1)],
    )
    expect(nodeOptions(g).map((o) => [o.value, o.group])).toEqual([
      ['a', 'Act 1'],
      ['b', 'Act 1'],
      ['z', 'Act 2'],
    ])
  })
})
