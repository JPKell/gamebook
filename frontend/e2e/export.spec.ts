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
