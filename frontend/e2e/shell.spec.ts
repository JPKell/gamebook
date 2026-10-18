import { expect, test } from '@playwright/test'

test('app shell loads and talks to the backend', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/story$/)
  await expect(page.getByRole('heading', { name: 'Story' })).toBeVisible()
  await expect(page.getByRole('status')).toHaveText(/Connected · v\d+\.\d+\.\d+/)
})

test('command palette navigates between sections', async ({ page }) => {
  await page.goto('/story')
  await page.keyboard.press('ControlOrMeta+k')
  await page.getByPlaceholder('Type a command or search…').fill('enemies')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/enemies$/)
  await expect(page.getByRole('heading', { name: 'Enemies' })).toBeVisible()
})

test('deep links survive a reload and preferences persist', async ({ page }) => {
  await page.goto('/mechanics')
  await expect(page.getByRole('heading', { name: 'Mechanics' })).toBeVisible()
  await page.getByRole('radio', { name: 'Advanced' }).click()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Mechanics' })).toBeVisible()
  await expect(page.getByRole('radio', { name: 'Advanced' })).toBeChecked()
})
