import { expect, type Page, test } from '@playwright/test'

/** Create a series + book through the Library and land on its canvas. */
async function newBook(page: Page, baseTitle: string) {
  // Unique per run so parallel/repeated tests never collide.
  const title = `${baseTitle} ${Math.random().toString(36).slice(2, 7)}`
  await page.goto('/library')
  await page
    .getByRole('button', { name: /New series|Create your first series/ })
    .first()
    .click()
  await page.getByLabel('Series title').fill(`${title} Series`)
  await page.getByRole('button', { name: 'Create series' }).click()
  const card = page.getByRole('region', { name: `${title} Series` })
  await card.getByRole('button', { name: 'New book' }).click()
  await page.getByLabel('Book title').fill(title)
  await page.getByRole('button', { name: 'Create book' }).click()
  await expect(page).toHaveURL(/\/story\/[0-9a-f-]+$/)
  await expect(nodeCard(page, 'Start')).toBeVisible()
  return title
}

function nodeCard(page: Page, title: string) {
  return page
    .locator('.react-flow__node-story')
    .filter({ has: page.getByText(title, { exact: true }) })
}

function edgeLabel(page: Page, text: string) {
  return page.locator('.react-flow__edgelabel-renderer').getByText(text, { exact: true })
}

test('author a linked node, undo/redo, and persist across reload', async ({ page }) => {
  await newBook(page, 'Undo Book')

  await page.getByRole('button', { name: 'Node', exact: true }).click()
  const title = page.getByRole('textbox', { name: 'Node title' })
  await expect(title).toHaveValue('Untitled')
  await title.fill('The Bridge')
  await title.press('Enter')
  await expect(nodeCard(page, 'The Bridge')).toBeVisible()

  await nodeCard(page, 'Start').click()
  await page.getByRole('tab', { name: /Choices/ }).click()
  await page.getByRole('button', { name: 'Add choice' }).click()
  await page.getByRole('textbox', { name: 'Choice text' }).fill('Cross over')
  await page.getByRole('textbox', { name: 'Choice text' }).press('Enter')
  await page
    .getByRole('combobox', { name: 'Destination node' })
    .selectOption({ label: 'The Bridge (the_bridge)' })
  await expect(edgeLabel(page, 'Cross over')).toBeVisible()

  // Undo the destination: the edge disappears; redo brings it back.
  await page.locator('.react-flow__pane').click()
  await page.keyboard.press('ControlOrMeta+z')
  await expect(edgeLabel(page, 'Cross over')).toHaveCount(0)
  await page.keyboard.press('ControlOrMeta+Shift+z')
  await expect(edgeLabel(page, 'Cross over')).toBeVisible()

  await page.reload()
  await expect(nodeCard(page, 'The Bridge')).toBeVisible()
  await expect(edgeLabel(page, 'Cross over')).toBeVisible()
  // The history also survives the reload.
  await expect(page.getByRole('button', { name: 'Undo', exact: true })).toBeEnabled()
})

test('problems panel navigates to the node, and delete is undoable', async ({ page }) => {
  await newBook(page, 'Problems Book')
  await page.keyboard.press('ControlOrMeta+j')
  const panel = page.getByRole('region', { name: 'Problems' })
  await expect(
    panel
      .getByText('“Start” has no choices', { exact: false })
      .or(panel.getByText(/Start' has no choices/)),
  ).toBeVisible()
  await panel.getByText(/has no choices/).click()
  await expect(page.getByRole('textbox', { name: 'Node title' })).toHaveValue('Start')

  await page.getByRole('button', { name: 'Node', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Node title' })).toHaveValue('Untitled')
  await page.getByRole('textbox', { name: 'Node title' }).fill('Doomed')
  await page.getByRole('textbox', { name: 'Node title' }).press('Enter')
  await nodeCard(page, 'Doomed').click()
  await page.keyboard.press('Delete')
  await expect(nodeCard(page, 'Doomed')).toHaveCount(0)
  await page.keyboard.press('ControlOrMeta+z')
  await expect(nodeCard(page, 'Doomed')).toBeVisible()
})

test('drag from a node handle to empty space creates a linked node', async ({ page }) => {
  await newBook(page, 'Drag Book')
  const handle = nodeCard(page, 'Start').locator('.react-flow__handle-right')
  const box = (await handle.boundingBox())!
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + 200, box.y + 40, { steps: 10 })
  await page.mouse.move(box.x + 320, box.y + 60, { steps: 10 })
  await page.mouse.up()
  await expect(page.getByRole('textbox', { name: 'Node title' })).toHaveValue('Untitled')
  await expect(page.locator('.react-flow__node-story')).toHaveCount(2)
  await expect(page.locator('.react-flow__edge')).toHaveCount(1)
})

test('live gbx feedback in the condition editor', async ({ page }) => {
  await newBook(page, 'Gbx Book')
  await nodeCard(page, 'Start').click()
  await page.getByRole('tab', { name: /Choices/ }).click()
  await page.getByRole('button', { name: 'Add choice' }).click()
  const condition = page.getByRole('textbox', { name: 'Condition' })
  await condition.click()
  await page.keyboard.type('GOLD >= 5 and tier >= medium')
  await expect(
    page.getByText('“your Gold is at least 5 and you are playing at the Medium tier or higher”'),
  ).toBeVisible()
  await page.keyboard.press('End')
  await page.keyboard.type(' and has(sword)')
  await expect(page.getByText(/Unknown item 'sword'/)).toBeVisible()
})
