/** Review regression: list edits must build on the latest value, not render-time props. */
import { screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { mockApi, renderApp } from '@/test/render'

afterEach(() => vi.restoreAllMocks())

const table = {
  id: 't1',
  key: 'road',
  name: 'Road',
  series_id: 's1',
  book_id: null,
  description: '',
  dice: '1d6',
  updated_at: '2026-01-01T00:00:00Z',
  entries: [{ lo: 1, hi: 6, kind: 'nothing', enemies: [], qty: 1, note: '' }],
}
const enemy = {
  id: 'e1',
  key: 'orc',
  name: 'Orc',
  series_id: 's1',
  book_id: null,
  description: '',
  default_level: 1,
  abilities: [{ name: 'Bite', description: '' }],
  loot: [],
  lore_entry_id: null,
  stat_formulas: {},
  tags: [],
  updated_at: 'x',
}
const base = {
  'GET /api/health': { status: 'ok', version: '1', database: 'ok' },
  'GET /api/series': [],
  'GET /api/series/s1': {
    id: 's1',
    key: 's',
    title: 'S',
    description: '',
    style: {},
    created_at: 'x',
    updated_at: 'x',
    books: [],
  },
  'GET /api/series/s1/rule-systems': [],
  'GET /api/series/s1/items': [],
  'GET /api/series/s1/flags': [],
  'GET /api/series/s1/item-totals': {},
  'GET /api/series/s1/entity-problems': {
    counts: { errors: 0, warnings: 0, info: 0 },
    problems: [],
  },
  'GET /api/series/s1/where-used': {
    target_type: 'table',
    target_key: 'road',
    refs: [],
    total_qty: null,
  },
  'POST /api/gbx/check': {
    ok: true,
    diagnostics: [],
    range: [1, 6],
    distribution: { '1': 1 / 6, '2': 1 / 6, '3': 1 / 6, '4': 1 / 6, '5': 1 / 6, '6': 1 / 6 },
  },
}

it('table: a note typed just before Add result is kept', async () => {
  let cur = structuredClone(table)
  const calls = mockApi({
    ...base,
    'GET /api/series/s1/enemies': [],
    'GET /api/series/s1/tables': () => [cur],
    'PATCH /api/tables/t1': ({ body }: { body: Partial<typeof cur> }) => {
      cur = { ...cur, ...body }
      return cur
    },
  })
  const { user } = renderApp('/enemies/s1?tab=tables&id=t1')
  const note = await screen.findByRole('textbox', { name: 'Note' })
  await user.click(note)
  await user.type(note, 'ambush')
  await user.click(screen.getByRole('button', { name: 'Add result' }))
  await waitFor(() => expect(calls.filter((c) => c.method === 'PATCH').length).toBe(2))
  await waitFor(() => expect(cur.entries).toHaveLength(2))
  expect(cur.entries[0]!.note).toBe('ambush')
})

it('enemy: an ability rename just before Add ability is kept', async () => {
  let cur = structuredClone(enemy)
  const calls = mockApi({
    ...base,
    'GET /api/series/s1/tables': [],
    'GET /api/series/s1/enemies': () => [cur],
    'PATCH /api/enemies/e1': ({ body }: { body: Partial<typeof cur> }) => {
      cur = { ...cur, ...body }
      return cur
    },
  })
  const { user } = renderApp('/enemies/s1?id=e1')
  const name = await screen.findByRole('textbox', { name: 'Ability name' })
  await user.clear(name)
  await user.type(name, 'Claw')
  await user.click(screen.getByRole('button', { name: 'Add ability' }))
  await waitFor(() => expect(calls.filter((c) => c.method === 'PATCH').length).toBe(2))
  await waitFor(() => expect(cur.abilities).toHaveLength(2))
  expect(cur.abilities.map((a) => a.name)).toEqual(['Claw', 'New ability'])
})
