import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { inflateRawSync } from 'node:zlib'

import { expect, type Page, test } from '@playwright/test'

const rand = () => Math.random().toString(36).slice(2, 7)

/** Minimal unzip (stored and deflated entries), enough for our own exports. */
function unzip(buf: Buffer, to: string) {
  const end = buf.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]))
  const count = buf.readUInt16LE(end + 10)
  let p = buf.readUInt32LE(end + 16)
  for (let i = 0; i < count; i++) {
    const method = buf.readUInt16LE(p + 10)
    const size = buf.readUInt32LE(p + 20)
    const nameLen = buf.readUInt16LE(p + 28)
    const extra = buf.readUInt16LE(p + 30)
    const comment = buf.readUInt16LE(p + 32)
    const local = buf.readUInt32LE(p + 42)
    const name = buf.toString('utf8', p + 46, p + 46 + nameLen)
    const start = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28)
    const raw = buf.subarray(start, start + size)
    const data = method === 0 ? raw : inflateRawSync(raw)
    mkdirSync(dirname(join(to, name)), { recursive: true })
    writeFileSync(join(to, name), data)
    p += 46 + nameLen + extra + comment
  }
}

/** Start → Fight the orc → Treasure (victory) / Dead (death), with prose. */
async function book(page: Page) {
  const r = page.request
  const series = (await (
    await r.post('/api/series', { data: { title: `Web ${rand()}` } })
  ).json()) as {
    id: string
  }
  const b = (await (
    await r.post(`/api/series/${series.id}/books`, { data: { title: `Quest ${rand()}` } })
  ).json()) as { id: string; start_node_id: string }
  const g = (await (await r.get(`/api/books/${b.id}/graph`)).json()) as {
    nodes: { act_id: string; variants: { id: string }[] }[]
  }
  const act = g.nodes[0]!.act_id
  const node = async (title: string, ending: string) => {
    const n = (await (
      await r.post(`/api/books/${b.id}/nodes`, { data: { act_id: act, title } })
    ).json()) as {
      id: string
    }
    await r.patch(`/api/nodes/${n.id}`, { data: { ending_kind: ending } })
    return n.id
  }
  const treasure = await node('Treasure', 'victory')
  const dead = await node('Dead', 'death')
  const orc = (await (
    await r.post(`/api/series/${series.id}/enemies`, {
      data: { name: 'Orc', stat_formulas: { SKILL: '1', STAMINA: '1' } },
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
  await r.post(`/api/variants/${g.nodes[0]!.variants[0]!.id}/prose`, {
    data: { text: 'A weak orc blocks the bridge.', approve: true },
  })
  return b.id
}

test('export the web player and play it from disk, with saves', async ({ page }) => {
  const bookId = await book(page)
  await page.goto(`/export/${bookId}`)
  const downloads = page.getByRole('region', { name: 'Download' })
  await downloads.getByRole('button', { name: 'Build web player' }).click()
  const link = downloads.getByRole('link', { name: /Download .*-web\.zip/ })
  await expect(link).toBeVisible({ timeout: 60_000 })
  const zip = await (await page.request.get((await link.getAttribute('href'))!)).body()
  const dir = mkdtempSync(join(tmpdir(), 'gamebook-web-'))
  unzip(zip, dir)

  await page.goto(`file://${dir}/index.html`)
  await page.getByRole('button', { name: 'Begin a new adventure' }).click()
  const story = page.getByRole('main', { name: 'Story' })
  await expect(story).toContainText('A weak orc blocks the bridge.')
  await page.getByRole('region', { name: 'Adventure sheet' }).getByText('Stamina').isVisible()

  page.once('dialog', (d) => void d.accept('Before the fight'))
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Saved')

  await page.getByRole('button', { name: 'Fight the orc' }).click()
  for (let i = 0; i < 50 && (await page.getByRole('button', { name: 'Attack' }).isVisible()); i++)
    await page.getByRole('button', { name: 'Attack' }).click()
  await expect(page.getByRole('region', { name: 'The end' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'What happened' })).toContainText(
    /won the fight|lost the fight/,
  )

  // Back undoes a move (the engine replays the rest exactly).
  await page.getByRole('button', { name: 'Go back a step' }).click()
  await expect(page.getByRole('region', { name: 'The end' })).toHaveCount(0)

  // Saves survive a reload; loading one restores the game.
  await page.reload()
  const saves = page.getByRole('region', { name: 'Saved games' })
  await expect(saves).toContainText('Before the fight')
  await expect(saves).toContainText('Autosave')
  await saves.getByRole('button', { name: /^Before the fight/ }).click()
  await expect(page.getByRole('button', { name: 'Fight the orc' })).toBeVisible()
})
