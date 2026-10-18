import { expect, type Page, test } from '@playwright/test'

const rand = () => Math.random().toString(36).slice(2, 7)

async function seriesWithBook(page: Page) {
  const r = page.request
  const series = (await (
    await r.post('/api/series', { data: { title: `Lore ${rand()}` } })
  ).json()) as {
    id: string
  }
  const book = (await (
    await r.post(`/api/series/${series.id}/books`, { data: { title: `Book ${rand()}` } })
  ).json()) as { id: string; start_node_id: string }
  return { seriesId: series.id, bookId: book.id, start: book.start_node_id }
}

test('characters and lore link to each other with [[mentions]]', async ({ page }) => {
  const { seriesId } = await seriesWithBook(page)
  await page.goto(`/lore/${seriesId}`)
  page.once('dialog', (d) => void d.accept('Mara Vell'))
  await page.getByRole('button', { name: 'New character' }).click()
  await expect(page.getByRole('heading', { name: 'Mara Vell' })).toBeVisible()
  await page.getByLabel('Role').fill('Witch')
  await page.getByLabel('Role').press('Enter')

  await page.getByRole('radio', { name: 'Places & lore' }).click()
  page.once('dialog', (d) => void d.accept('The Crypt'))
  await page.getByRole('button', { name: 'New entry' }).click()
  await page.getByLabel('Type').selectOption('location')
  const text = page.getByLabel('Text')
  await text.fill('Where [[mara_vell|the witch]] hides from [[nobody]].')
  await text.blur()
  const preview = page.getByRole('link', { name: 'the witch' })
  await expect(preview).toBeVisible()
  await expect(page.getByText('nobody', { exact: true })).toHaveAttribute(
    'title',
    /Nothing is called/,
  )

  await preview.click()
  await expect(page.getByRole('heading', { name: 'Mara Vell' })).toBeVisible()
  const mentioned = page.getByRole('region', { name: 'Mentioned in' })
  await expect(mentioned.getByRole('link', { name: 'The Crypt' })).toBeVisible()
})

test('outline beats link nodes and show in the inspector digest', async ({ page }) => {
  const { seriesId, bookId, start } = await seriesWithBook(page)
  await page.request.patch(`/api/nodes/${start}`, {
    data: { on_enter: [{ op: 'set_flag', flag: 'RAVEN' }] },
  })
  const graph = (await (await page.request.get(`/api/books/${bookId}/graph`)).json()) as {
    nodes: { act_id: string }[]
  }
  const hall = (await (
    await page.request.post(`/api/books/${bookId}/nodes`, {
      data: { act_id: graph.nodes[0]!.act_id, title: 'Hall', link_from: { node_id: start } },
    })
  ).json()) as { id: string }
  const end = (await (
    await page.request.post(`/api/books/${bookId}/nodes`, {
      data: { act_id: graph.nodes[0]!.act_id, title: 'Vault' },
    })
  ).json()) as { id: string }
  for (const [label, condition] of [
    ['Unlock', 'has(silver_key)'],
    ['Call the raven', 'flag(RAVEN)'],
  ]) {
    await page.request.post(`/api/nodes/${hall.id}/choices`, {
      data: { label, condition, target_node_id: end.id },
    })
  }

  await page.goto(`/lore/${seriesId}?tab=outline`)
  await page.getByRole('button', { name: 'Add beat' }).click()
  const beat = page.getByRole('listitem', { name: /Beat 1/ })
  await beat.getByLabel('Beat title').fill('The descent')
  await beat.getByLabel('Beat title').press('Enter')
  await beat.getByLabel('Link a node').selectOption({ label: 'Hall' })
  await expect(beat.getByRole('link', { name: 'Hall' })).toBeVisible()
  await expect(page.getByText('Not in any beat yet:')).toContainText('Start')

  await page.goto(`/story/${bookId}?node=${hall.id}`)
  await page.getByRole('tab', { name: 'Digest' }).click()
  await expect(page.getByRole('region', { name: 'Every reader has' })).toContainText('RAVEN')
  const gates = page.getByRole('region', { name: 'Gated choices' })
  await expect(gates.getByRole('listitem').filter({ hasText: 'Unlock' })).toContainText(
    'No reader can take it',
  )
  await expect(gates.getByRole('listitem').filter({ hasText: 'Call the raven' })).toContainText(
    'Every reader can take it',
  )
  await expect(page.getByRole('region', { name: 'Story beats' })).toContainText('The descent')
  await expect(page.getByRole('region', { name: 'Story so far' })).toContainText('Start')
})
