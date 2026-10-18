import { expect, type Page, test } from '@playwright/test'

const rand = () => Math.random().toString(36).slice(2, 7)

async function newSeries(page: Page) {
  const res = await page.request.post('/api/series', { data: { title: `Bestiary ${rand()}` } })
  return ((await res.json()) as { id: string }).id
}

test('create an enemy, write formulas and read the level table', async ({ page }) => {
  const id = await newSeries(page)
  await page.goto(`/enemies/${id}`)
  page.once('dialog', (d) => void d.accept('Cave Troll'))
  await page.getByRole('button', { name: 'New enemy' }).click()
  await expect(page.getByRole('heading', { name: 'Cave Troll' })).toBeVisible()
  await expect(page).toHaveURL(/\?id=/)

  // Basic tier asks enemies for SKILL and STAMINA; neither has a formula yet.
  await expect(page.getByText(/No formula for .*SKILL/)).toBeVisible()
  const skill = page.getByRole('textbox', { name: 'SKILL formula' })
  await skill.click()
  await page.keyboard.type('5 + level')
  await page.keyboard.press('Enter')
  const table = page.getByRole('table', { name: /stats by level/ })
  await expect(table.getByRole('row').nth(3)).toContainText('8') // level 3 → 5 + 3

  await page.reload()
  await expect(page.getByRole('textbox', { name: 'SKILL formula' })).toHaveText('5 + level')
  await expect(page.getByRole('button', { name: /Cave Troll/ })).toBeVisible()
})

test('random table shows gaps, overlaps and chances', async ({ page }) => {
  const id = await newSeries(page)
  await page.request.post(`/api/series/${id}/tables`, {
    data: {
      name: 'Road',
      dice: '1d6',
      entries: [
        { lo: 1, hi: 3, kind: 'nothing' },
        { lo: 3, hi: 4, kind: 'gold', amount: '1d6' },
      ],
    },
  })
  await page.goto(`/enemies/${id}?tab=tables`)
  await page.getByRole('button', { name: /Road/ }).click()
  await expect(page.getByText('Nothing happens on 5–6')).toBeVisible()
  await expect(page.getByText(/Several results share 3/)).toBeVisible()
  await expect(page.getByTitle('Chance of this result').first()).toHaveText('50%')

  const second = page.getByRole('group', { name: 'Result 2' })
  await second.getByLabel('From').fill('4')
  await second.getByLabel('From').press('Enter')
  await second.getByLabel('To').fill('6')
  await second.getByLabel('To').press('Enter')
  await expect(page.getByText('Every roll has exactly one result')).toBeVisible()
})

test('item totals and where-used deep link into the story', async ({ page }) => {
  const id = await newSeries(page)
  const book = (await (
    await page.request.post(`/api/series/${id}/books`, { data: { title: `Book ${rand()}` } })
  ).json()) as { id: string; start_node_id: string }
  const item = (await (
    await page.request.post(`/api/series/${id}/items`, { data: { name: 'Rope', stackable: true } })
  ).json()) as { id: string }
  await page.request.put(`/api/nodes/${book.start_node_id}/items`, {
    data: [{ item_id: item.id, qty: 3 }],
  })

  await page.goto(`/items/${id}`)
  const row = page.getByRole('button', { name: /Rope/ })
  await expect(row).toContainText('×3')
  await row.click()
  const placements = page.getByRole('region', { name: 'Placements' })
  await expect(placements.getByText('in the game across 1 reference')).toBeVisible()
  await placements.getByRole('link', { name: 'Start' }).click()
  await expect(page).toHaveURL(new RegExp(`/story/${book.id}$`))
  await expect(page.getByRole('textbox', { name: 'Node title' })).toHaveValue('Start')
  // The canvas centres on the node (zoom 1.1) instead of the initial fit-to-view.
  await expect(page.locator('.react-flow__viewport')).toHaveAttribute('style', /scale\(1\.1\)/)
})
