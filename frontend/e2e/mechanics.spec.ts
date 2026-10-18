import { expect, type Page, test } from '@playwright/test'

async function newSeries(page: Page) {
  const title = `Rules ${Math.random().toString(36).slice(2, 7)}`
  const res = await page.request.post('/api/series', { data: { title } })
  const series = (await res.json()) as { id: string }
  await page.request.post(`/api/series/${series.id}/enemies`, {
    data: {
      name: 'Orc',
      stat_formulas: { SKILL: '5 + level', STAMINA: '4 + level * 2', ARMOR: 'floor(level / 2)' },
    },
  })
  return series.id
}

function statRow(page: Page, key: string) {
  return page
    .getByRole('region', { name: 'Stats & resources' })
    .locator('div.rounded-lg')
    .filter({ hasText: key })
    .first()
}

test('override and revert an inherited stat', async ({ page }) => {
  const id = await newSeries(page)
  await page.goto(`/mechanics/${id}?tier=medium`)
  const skill = statRow(page, 'SKILL')
  await expect(skill.getByText('from Basic')).toBeVisible()
  await skill.getByRole('button', { name: 'Override' }).click()
  await expect(skill.getByText('overrides Basic')).toBeVisible()
  const label = page.getByRole('region', { name: 'Stats & resources' }).getByLabel('Label').first()
  await label.fill('Prowess')
  await label.press('Enter')
  await expect(skill).toContainText('Prowess')

  await page.reload()
  await expect(statRow(page, 'SKILL')).toContainText('Prowess')
  await expect(statRow(page, 'SKILL').getByText('overrides Basic')).toBeVisible()
  await statRow(page, 'SKILL').getByRole('button', { name: 'Revert' }).click()
  await expect(statRow(page, 'SKILL').getByText('from Basic')).toBeVisible()
  await expect(statRow(page, 'SKILL')).toContainText('Skill')
})

test('combat lab runs fights and plots a difficulty curve', async ({ page }) => {
  const id = await newSeries(page)
  await page.goto(`/mechanics/${id}?tier=basic&view=lab`)
  await page.getByRole('button', { name: /Run 2,000 fights/ }).click()
  const results = page.getByRole('region', { name: 'Lab results' })
  await expect(results.getByText('Player wins')).toBeVisible()
  await expect(results.getByText(/^\d+(\.\d)?%$/).first()).toBeVisible()
  await expect(page.getByRole('img', { name: 'Rounds per fight histogram' })).toBeVisible()

  await page.getByLabel('Enemy', { exact: true }).selectOption({ label: 'Orc' })
  await page.getByRole('checkbox', { name: /Compare tiers/ }).check()
  await page.getByRole('button', { name: 'Plot win rate by level' }).click()
  await expect(page.getByRole('img', { name: 'Win rate against Orc by level' })).toBeVisible({
    timeout: 20_000,
  })
  await expect(page.getByRole('list', { name: 'Legend' })).toContainText('Basic')
})

test('add a tier that inherits from the last one', async ({ page }) => {
  const id = await newSeries(page)
  await page.goto(`/mechanics/${id}`)
  page.once('dialog', (d) => void d.accept('Nightmare'))
  await page.getByRole('button', { name: 'Add tier' }).click()
  const tab = page.getByRole('tab', { name: /Nightmare/ })
  await expect(tab).toHaveAttribute('aria-selected', 'true')
  await expect(tab).toContainText('+Advanced')
  await expect(statRow(page, 'ARMOR').getByText('from Medium')).toBeVisible()
})
