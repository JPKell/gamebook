import { deflateSync } from 'node:zlib'

import { expect, type Page, test } from '@playwright/test'

const rand = () => Math.random().toString(36).slice(2, 7)

const CRC = Array.from({ length: 256 }, (_, n) => {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  return c >>> 0
})
function crc32(buf: Buffer) {
  let c = 0xffffffff
  for (const b of buf) c = CRC[(c ^ b) & 0xff]! ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}
function chunk(type: string, data: Buffer) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const td = Buffer.concat([Buffer.from(type, 'ascii'), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(td))
  return Buffer.concat([len, td, crc])
}
/** A solid-colour PNG of the given size (so DPI maths are real). */
function png(width: number, height: number, rgb: [number, number, number] = [180, 40, 40]) {
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(width, 0)
  ihdr.writeUInt32BE(height, 4)
  ihdr.set([8, 2, 0, 0, 0], 8)
  const row = Buffer.alloc(1 + width * 3)
  for (let x = 0; x < width; x++) row.set(rgb, 1 + x * 3)
  const raw = Buffer.concat(Array.from({ length: height }, () => row))
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

/** A series and book with an orc encounter on the start section. */
async function setup(page: Page) {
  const r = page.request
  const series = (await (
    await r.post('/api/series', { data: { title: `Art ${rand()}` } })
  ).json()) as {
    id: string
  }
  const book = (await (
    await r.post(`/api/series/${series.id}/books`, { data: { title: `Book ${rand()}` } })
  ).json()) as { id: string; start_node_id: string }
  const orc = (await (
    await r.post(`/api/series/${series.id}/enemies`, {
      data: { name: 'Orc', stat_formulas: { SKILL: '5 + level', STAMINA: '4 + level * 2' } },
    })
  ).json()) as { id: string }
  await r.post(`/api/nodes/${book.start_node_id}/encounters`, {
    data: { label: 'Orc', enemies: [{ enemy_id: orc.id, level: 2 }] },
  })
  return { seriesId: series.id, bookId: book.id, start: book.start_node_id }
}

test('upload to the library, place an illustration and watch its DPI', async ({ page }) => {
  const s = await setup(page)
  await page.goto(`/art/${s.seriesId}`)
  await page.getByLabel('Upload images').setInputFiles([
    { name: 'gate.png', mimeType: 'image/png', buffer: png(1200, 900) },
    { name: 'hall.png', mimeType: 'image/png', buffer: png(400, 300, [30, 90, 160]) },
  ])
  await expect(page.getByRole('status').filter({ hasText: 'Added 2 image(s)' })).toBeVisible()
  await page.getByRole('list', { name: 'Images' }).getByRole('button', { name: 'gate.png' }).click()
  await page.getByLabel('Alt text').fill('A stone gate at dusk')
  await page.getByLabel('Caption').click() // blur commits
  await expect(page.getByRole('region', { name: "Where it's used" })).toContainText('Not used')

  // Place it on the start section from the inspector's Art tab.
  await page.goto(`/story/${s.bookId}?node=${s.start}`)
  await page.getByRole('tab', { name: 'Art' }).click()
  await page.getByRole('button', { name: 'Add image' }).click()
  await page.getByRole('button', { name: 'Use gate.png' }).click()
  const list = page.getByRole('region', { name: 'Artwork for Start' })
  await expect(list).toContainText('print-ready')
  await page.getByLabel('Size').selectOption('full_width')
  await expect(list.getByText(/dpi · soft in print/).first()).toBeVisible()
  await page.getByLabel('Size').selectOption('vignette')
  await expect(list.getByText(/dpi · print-ready/).first()).toBeVisible()
  await expect(
    page.locator('.react-flow__node-story').filter({ hasText: 'Start' }).locator('img'),
  ).toBeVisible()

  // Problems list a low-res placement, and the library knows where it's used.
  await page.getByLabel('Size').selectOption('full_width')
  await page.goto(`/art/${s.seriesId}`)
  await page.getByRole('list', { name: 'Images' }).getByRole('button', { name: 'gate.png' }).click()
  await expect(page.getByRole('region', { name: "Where it's used" })).toContainText(
    'Illustration: Start',
  )
})

test('act opener placeholder, maps with markers, and the shot list', async ({ page }) => {
  const s = await setup(page)
  await page.request.post(`/api/series/${s.seriesId}/assets?filename=valley.png`, {
    data: png(800, 500, [60, 140, 60]),
    headers: { 'Content-Type': 'image/png' },
  })
  await page.goto(`/art/${s.seriesId}?view=book&book=${s.bookId}`)
  const openers = page.getByRole('region', { name: 'Opener for Act 1' })
  await openers.getByRole('button', { name: 'Add placeholder' }).click()
  await page.getByLabel('Brief for the illustrator').fill('Storm over the valley')
  await page.getByLabel('Caption').click()
  await expect(openers).toContainText('Placeholder')

  await page.getByRole('radio', { name: 'Commissioning' }).click()
  await expect(page.getByRole('table')).toContainText('Storm over the valley')
  await expect(page.getByRole('link', { name: /Shot list/ })).toHaveAttribute('href', /format=md/)

  await page.getByRole('radio', { name: 'Maps' }).click()
  await page.getByRole('button', { name: 'New map' }).click()
  await page.getByLabel('Book').last().selectOption(s.bookId)
  await page.getByRole('button', { name: 'Choose image' }).click()
  await page.getByRole('button', { name: 'Use valley.png' }).click()
  const map = page.getByRole('img', { name: /valley|Map 1/ })
  await map.click({ position: { x: 60, y: 40 } })
  await expect(page.getByRole('button', { name: /^Marker 1:/ })).toBeVisible()
  await page.getByLabel('Label', { exact: true }).fill('The Gate')
  await page.getByLabel('Label', { exact: true }).press('Enter')
  await page.getByLabel('Links to section').selectOption({ label: 'Start' })

  // The player shows the map with the reader's position.
  await page.goto(`/playtest/${s.bookId}?view=play`)
  const panel = page.getByRole('region', { name: 'Map' })
  await expect(panel).toContainText('The Gate (you are here)')
})

test('appendix builder previews a tier bestiary and the codex unlocks entries', async ({
  page,
}) => {
  const s = await setup(page)
  await page.goto(`/art/${s.seriesId}?view=appendices&book=${s.bookId}`)
  await page.getByRole('button', { name: 'Add' }).click()
  const preview = page.frameLocator('iframe[title="Preview of Bestiary"]')
  await expect(preview.getByRole('heading', { name: 'Orc' })).toBeVisible()
  await expect(preview.locator('body')).toContainText('7') // SKILL 5 + level 2

  await page.getByLabel('Appendix kind').selectOption('sheet')
  await page.getByRole('button', { name: 'Add' }).click()
  const sheet = page.frameLocator('iframe[title="Preview of Adventure Sheet"]')
  await expect(sheet.getByRole('heading', { name: 'Inventory' })).toBeVisible()

  // In the player the bestiary starts empty and fills in once the orc is fought.
  await page.goto(`/playtest/${s.bookId}?view=play`)
  const codex = page.getByRole('region', { name: 'Codex' })
  await codex.getByRole('button', { name: 'Codex' }).click()
  await expect(codex.frameLocator('iframe').locator('body')).toContainText('0 of 1 creatures met')
})
