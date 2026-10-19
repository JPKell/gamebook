import { expect, type Page, test } from '@playwright/test'

const rand = () => Math.random().toString(36).slice(2, 7)

/** start → left (gives rope) | right → gate → end, wired to the offline model. */
async function setup(page: Page) {
  const r = page.request
  const series = (await (
    await r.post('/api/series', { data: { title: `Assist ${rand()}` } })
  ).json()) as {
    id: string
  }
  const book = (await (
    await r.post(`/api/series/${series.id}/books`, { data: { title: `Book ${rand()}` } })
  ).json()) as { id: string; start_node_id: string }
  const provider = (await (
    await r.post('/api/llm/providers', {
      data: { name: `Offline ${rand()}`, kind: 'fake', models: [{ id: 'offline' }] },
    })
  ).json()) as { id: string }
  await r.put(`/api/series/${series.id}/writing-settings`, {
    data: { roles: { writer: { provider_id: provider.id, model: 'offline' } } },
  })
  await r.post(`/api/series/${series.id}/items`, { data: { name: 'Rope' } })
  const g = (await (await r.get(`/api/books/${book.id}/graph`)).json()) as {
    nodes: { act_id: string; x: number; y: number }[]
  }
  const act = g.nodes[0]!.act_id
  const node = async (title: string, from: string, x: number, y: number) =>
    (await (
      await r.post(`/api/books/${book.id}/nodes`, {
        data: { act_id: act, title, x, y, link_from: { node_id: from, label: `To ${title}` } },
      })
    ).json()) as { id: string }
  const left = await node('Left', book.start_node_id, 320, -100)
  const right = await node('Right', book.start_node_id, 320, 100)
  await r.patch(`/api/nodes/${left.id}`, { data: { on_enter: [{ op: 'give', item: 'rope' }] } })
  const gate = await node('Gate', left.id, 640, 0)
  await r.post(`/api/nodes/${right.id}/choices`, { data: { label: 'On', target_node_id: gate.id } })
  const end = await node('End', gate.id, 960, 0)
  await r.patch(`/api/nodes/${end.id}`, { data: { ending_kind: 'victory' } })
  const variants = new Map(
    (
      (await (await r.get(`/api/books/${book.id}/graph`)).json()) as {
        nodes: { id: string; variants: { id: string }[] }[]
      }
    ).nodes.map((n) => [n.id, n.variants[0]!.id]),
  )
  return {
    seriesId: series.id,
    bookId: book.id,
    act,
    start: book.start_node_id,
    gate: gate.id,
    variants,
  }
}

test('suggested sections appear dashed on the canvas and can be added', async ({ page }) => {
  const s = await setup(page)
  await page.request.post(`/api/acts/${s.act}/beats`, {
    data: { title: 'Ambush', description: 'Bandits strike.' },
  })
  await page.goto(`/story/${s.bookId}`)
  await page.getByRole('button', { name: 'Suggest', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Suggest' }).click()
  await expect(page.getByRole('status').filter({ hasText: /Suggested 1 section/ })).toBeVisible({
    timeout: 20_000,
  })
  await page.keyboard.press('Escape')

  const ghost = page.getByLabel('Suggested section: Ambush')
  await expect(ghost).toBeVisible()
  await expect(page.getByRole('region', { name: 'Suggestions' })).toContainText('End')
  await ghost.getByRole('button', { name: 'Add section' }).click()
  await expect(page.locator('.react-flow__node-story').filter({ hasText: 'Ambush' })).toBeVisible()
  await expect(ghost).toHaveCount(0)
  await page
    .getByRole('button', { name: /^Add choice/ })
    .first()
    .click()
  await expect(page.getByRole('button', { name: /^Add choice/ })).toHaveCount(1)
  await page.getByRole('button', { name: 'Add all' }).click()
  await expect(page.getByRole('region', { name: 'Suggestions' })).toHaveCount(0, {
    timeout: 10_000,
  })
})

test('consistency check flags prose that assumes an item', async ({ page }) => {
  const s = await setup(page)
  await page.request.post(`/api/variants/${s.variants.get(s.gate)}/prose`, {
    data: { text: 'You tie your rope to the gate and climb.', approve: true },
  })
  await page.goto(`/writing/${s.bookId}?variant=${s.variants.get(s.gate)}`)
  const panel = page.getByRole('region', { name: 'Consistency' })
  await panel.getByRole('button', { name: 'Check this section' }).click()
  await expect(panel).toContainText('only some readers do', { timeout: 20_000 })
  await expect(panel).toContainText('You tie your rope to the gate and climb.')
  await panel.getByRole('button', { name: 'Dismiss' }).click()
  await expect(panel).not.toContainText('only some readers do')
})

test('lore extracted from prose is reviewed and created', async ({ page }) => {
  const s = await setup(page)
  await page.request.post(`/api/variants/${s.variants.get(s.start)}/prose`, {
    data: { text: 'A woman named Mara waits by the arch called the Iron Gate.', approve: true },
  })
  await page.goto(`/lore/${s.seriesId}?tab=drafts`)
  await page.getByRole('button', { name: 'Read the prose' }).click()
  const place = page.getByRole('listitem', { name: 'New location: Iron Gate' })
  await expect(place).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('listitem', { name: 'New character: Mara' })).toBeVisible()
  await place.getByLabel('Text').fill('An arch of black iron.')
  await place.getByRole('button', { name: 'Create' }).click()
  await expect(place).toHaveCount(0)
  await page.getByRole('radio', { name: 'Places & lore' }).click()
  await page.getByRole('button', { name: /Iron Gate/ }).click()
  await expect(page.getByLabel('Text')).toHaveValue('An arch of black iron.')
})
