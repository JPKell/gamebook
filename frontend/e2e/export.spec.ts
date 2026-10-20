import { expect, type Page, test } from '@playwright/test'

const rand = () => Math.random().toString(36).slice(2, 7)

/** Start → fight an orc or test your luck → Treasure (victory) / Dead (death). */
async function book(page: Page) {
  const r = page.request
  const series = (await (
    await r.post('/api/series', { data: { title: `Print ${rand()}` } })
  ).json()) as {
    id: string
  }
  const b = (await (
    await r.post(`/api/series/${series.id}/books`, { data: { title: `Quest ${rand()}` } })
  ).json()) as { id: string; start_node_id: string }
  const graph = (await (await r.get(`/api/books/${b.id}/graph`)).json()) as {
    nodes: { id: string; act_id: string; variants: { id: string }[] }[]
  }
  const act = graph.nodes[0]!.act_id
  const node = async (title: string, ending: string) => {
    const n = (await (
      await r.post(`/api/books/${b.id}/nodes`, { data: { act_id: act, title } })
    ).json()) as { id: string }
    await r.patch(`/api/nodes/${n.id}`, { data: { ending_kind: ending } })
    return n.id
  }
  const treasure = await node('Treasure', 'victory')
  const dead = await node('Dead', 'death')
  const orc = (await (
    await r.post(`/api/series/${series.id}/enemies`, {
      data: { name: 'Orc', stat_formulas: { SKILL: '5 + level', STAMINA: '4 + level * 2' } },
    })
  ).json()) as { id: string }
  const enc = (await (
    await r.post(`/api/nodes/${b.start_node_id}/encounters`, {
      data: { label: 'Orc', enemies: [{ enemy_id: orc.id, level: 1 }] },
    })
  ).json()) as { id: string }
  const fight = (await (
    await r.post(`/api/nodes/${b.start_node_id}/choices`, {
      data: { label: 'Fight the orc', kind: 'combat' },
    })
  ).json()) as { id: string }
  await r.patch(`/api/choices/${fight.id}`, {
    data: {
      encounter_id: enc.id,
      outcomes: [
        { key: 'win', target_node_id: treasure },
        { key: 'lose', target_node_id: dead },
      ],
    },
  })
  await r.post(`/api/variants/${graph.nodes[0]!.variants[0]!.id}/prose`, {
    data: { text: 'An orc blocks the bridge.', approve: true },
  })
  return b.id
}

test('pre-flight, verify, build a PDF and read the proof', async ({ page }) => {
  const bookId = await book(page)
  await page.goto(`/export/${bookId}`)
  const pre = page.getByRole('region', { name: 'Pre-flight' })
  await expect(pre).toContainText('Sections')
  await expect(pre).toContainText('has no approved prose')

  const proof = page.frameLocator('iframe[title="Print proof"]')
  await expect(proof.getByText('An orc blocks the bridge.')).toBeVisible()
  await expect(proof.getByRole('cell', { name: /^ORC/ })).toBeVisible()
  await expect(proof.getByText(/If you win, turn to/)).toBeVisible()

  const verify = page.getByRole('region', { name: 'Verify the printed book' })
  await verify.getByRole('button', { name: 'Verify' }).click()
  await expect(verify.getByRole('status')).toContainText('Verified', { timeout: 20_000 })

  const downloads = page.getByRole('region', { name: 'Download' })
  await downloads.getByRole('button', { name: 'Build PDF' }).click()
  const link = downloads.getByRole('link', { name: /Download .*\.pdf/ })
  await expect(link).toBeVisible({ timeout: 60_000 })
  const res = await page.request.get((await link.getAttribute('href'))!)
  expect(res.headers()['content-type']).toBe('application/pdf')

  await downloads.getByRole('button', { name: 'Build EPUB' }).click()
  await expect(downloads.getByRole('link', { name: /Download .*\.epub/ })).toBeVisible({
    timeout: 60_000,
  })
})

test('lay out the page: styles, running heads and folded sheets', async ({ page }) => {
  const bookId = await book(page)
  const setup = async () =>
    (await (await page.request.get(`/api/books/${bookId}/page-setup`)).json()) as {
      styles: Record<string, { size_pt?: number | null; italic?: boolean | null }>
      gutter_mm: number
      header: { verso: { left: string }; recto: { right: string } }
      imposition: { fold: boolean; signature_pages: number }
      trim_width_mm: number
    }
  await page.goto(`/export/${bookId}`)
  await page.getByRole('link', { name: 'Page layout' }).click()
  await expect(page.getByRole('heading', { name: 'Page layout' })).toBeVisible()
  await expect(page.locator('iframe[title="Layout sample"]')).toBeVisible()

  // Page: the gutter.
  await page.getByLabel('Gutter (mm)').fill('6')
  await page.getByLabel('Gutter (mm)').press('Enter')
  await expect.poll(async () => (await setup()).gutter_mm).toBe(6)

  // Text: section numbers bigger and italic.
  await page.getByRole('tab', { name: 'Text' }).click()
  await page.getByRole('button', { name: 'Section numbers' }).click()
  await page.getByLabel('Size (pt)').fill('22')
  await page.getByLabel('Size (pt)').press('Enter')
  await page.getByLabel(/^Italic/).selectOption('on')
  await expect
    .poll(async () => (await setup()).styles.section)
    .toMatchObject({ size_pt: 22, italic: true })

  // Headers: section numbers on the outside edges.
  await page.getByRole('tab', { name: 'Headers & footers' }).click()
  await page.getByLabel('Header preset').selectOption('sections_outside')
  await expect
    .poll(async () => {
      const h = (await setup()).header
      return [h.verso.left, h.recto.right]
    })
    .toEqual(['section_first', 'section_last'])

  // Signatures: Letter folded in half, 8-page signatures.
  await page.getByRole('tab', { name: 'Signatures' }).click()
  // Edits reach React a tick after the click (the query cache notifies asynchronously).
  const fold = page.getByLabel('Each sheet holds 2 pages per side (folded)')
  await fold.click()
  await expect(fold).toBeChecked()
  await page.getByLabel('Pages per signature').selectOption('8')
  await expect
    .poll(async () => {
      const s = await setup()
      return [s.imposition.fold, s.imposition.signature_pages, s.trim_width_mm]
    })
    .toEqual([true, 8, 139.7])
  await expect(page.getByRole('tabpanel').getByText('Pages: 139.7 × 215.9 mm')).toBeVisible()

  // Export builds the sheets.
  await page.getByRole('main').getByRole('link', { name: 'Export' }).click()
  const downloads = page.getByRole('region', { name: 'Download' })
  await expect(downloads.getByLabel(/PDF on folded sheets/)).toBeChecked()
  await downloads.getByRole('button', { name: 'Build PDF' }).click()
  await expect(downloads.getByRole('link', { name: /Download .*-sheets\.pdf/ })).toBeVisible({
    timeout: 60_000,
  })
  await expect(downloads).toContainText(/sheets in \d+ signature/)
})
