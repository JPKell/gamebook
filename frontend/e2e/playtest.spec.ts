import { expect, type Page, test } from '@playwright/test'

const rand = () => Math.random().toString(36).slice(2, 7)

/** Start → fight an orc, or test your luck → Treasure (victory) / Dead (death). */
async function playableBook(page: Page) {
  const r = page.request
  const series = (await (
    await r.post('/api/series', { data: { title: `Play ${rand()}` } })
  ).json()) as {
    id: string
  }
  const book = (await (
    await r.post(`/api/series/${series.id}/books`, { data: { title: `Quest ${rand()}` } })
  ).json()) as { id: string; start_node_id: string }
  const graph = (await (await r.get(`/api/books/${book.id}/graph`)).json()) as {
    nodes: { id: string; act_id: string }[]
  }
  const act = graph.nodes[0]!.act_id
  const start = book.start_node_id
  await r.patch(`/api/nodes/${start}`, { data: { beat_notes: 'An orc blocks the bridge.' } })
  const node = async (title: string, ending: string) => {
    const n = (await (
      await r.post(`/api/books/${book.id}/nodes`, { data: { act_id: act, title } })
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
      data: { name: 'Orc', stat_formulas: { SKILL: '5 + level', STAMINA: '4 + level * 2' } },
    })
  ).json()) as { id: string }
  const enc = (await (
    await r.post(`/api/nodes/${start}/encounters`, {
      data: { label: 'Orc', enemies: [{ enemy_id: orc.id, level: 1 }] },
    })
  ).json()) as { id: string }
  const fight = (await (
    await r.post(`/api/nodes/${start}/choices`, {
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
  const luck = (await (
    await r.post(`/api/nodes/${start}/choices`, {
      data: { label: 'Sneak past', kind: 'test', test: 'luck' },
    })
  ).json()) as { id: string }
  await r.patch(`/api/choices/${luck.id}`, {
    data: {
      outcomes: [
        { key: 'success', target_node_id: treasure },
        { key: 'failure', target_node_id: dead },
      ],
    },
  })
  return { bookId: book.id, start, treasure, dead }
}

test('play a book to an ending, go back, and use the debug drawer', async ({ page }) => {
  const { bookId } = await playableBook(page)
  await page.goto(`/playtest/${bookId}?view=play`)
  const scene = page.getByRole('region', { name: 'Scene' })
  await expect(scene.getByRole('heading', { name: 'Start' })).toBeVisible()
  await expect(scene.getByText('An orc blocks the bridge.')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Adventure sheet' })).toContainText('Stamina')

  await page.getByRole('button', { name: /Fight the orc/ }).click()
  const combat = page.getByRole('region', { name: 'Combat' })
  await expect(combat).toContainText('Orc')
  for (let i = 0; i < 60 && (await combat.isVisible()); i++) {
    await page.getByRole('button', { name: /Attack/ }).click()
    await page.waitForResponse((r) => r.url().endsWith('/play'))
  }
  await expect(page.getByRole('status').filter({ hasText: /Victory|You died/ })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Dice log' })).toContainText('Round 1')

  // Back undoes the last move; reload keeps the session.
  await page.getByRole('button', { name: 'Back' }).click()
  await expect(page.getByRole('status').filter({ hasText: /Victory|You died/ })).toHaveCount(0)
  await page.reload()
  await expect(page.getByRole('region', { name: 'Combat' })).toBeVisible()

  // Debug: force a lucky roll, then sneak past.
  await page.getByRole('button', { name: 'Restart' }).click()
  await page.getByRole('button', { name: 'Debug drawer' }).click()
  const force = page.getByLabel('Force the next roll')
  await force.fill('2')
  await force.press('Enter')
  await page.getByRole('button', { name: /Sneak past/ }).click()
  await expect(scene.getByRole('heading', { name: 'Treasure' })).toBeVisible()
  await expect(scene).toContainText('success (rolled 2)')
})

test('run a bot batch, read the dashboard, replay a run and see heat on the canvas', async ({
  page,
}) => {
  const { bookId } = await playableBook(page)
  await page.goto(`/playtest/${bookId}`)
  const form = page.getByRole('region', { name: 'New batch' })
  await form.getByLabel('Runs').fill('400')
  await form.getByLabel('Runs').press('Enter')
  await form.getByLabel('Label').fill('First pass')
  await form.getByLabel('Label').press('Enter')
  await form.getByRole('button', { name: /Run 400 games/ }).click()

  await expect(page.getByRole('heading', { name: 'First pass' })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('list', { name: 'Outcomes' })).toContainText('Victory')
  await expect(page.getByRole('region', { name: 'Deadliest nodes' })).toContainText('Dead')
  await expect(page.getByRole('region', { name: 'Enemies' })).toContainText('Orc')

  await page.getByRole('button', { name: 'Replay run 1', exact: true }).click()
  const replay = page.getByRole('region', { name: 'Replay of run 1' })
  await expect(replay).toBeVisible()
  await replay.getByRole('button', { name: 'First step' }).click()
  await expect(replay.getByText(/Step 0 \//)).toBeVisible()
  await expect(replay.getByRole('heading', { name: 'Start' })).toBeVisible()
  await expect(replay.getByText('Next, the bot chose:')).toBeVisible()

  // A second batch to compare against.
  await form.getByLabel('Bot').selectOption('cautious')
  await form.getByRole('button', { name: /Run 400 games/ }).click()
  await expect(page.getByRole('heading', { name: /400 cautious/ })).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Compare with First pass' }).click()
  await expect(page.getByRole('region', { name: 'Batch comparison' })).toContainText('Win rate')

  await page.getByRole('link', { name: 'Show heat on the canvas' }).click()
  await expect(page).toHaveURL(new RegExp(`/story/${bookId}\\?heat=`))
  await expect(page.getByRole('status').filter({ hasText: 'Playtest heat' })).toBeVisible()
  await expect(page.locator('.react-flow__node-story').filter({ hasText: 'Start' })).toContainText(
    '100%',
  )
})

test('coverage walk finds unreachable content', async ({ page }) => {
  const { bookId } = await playableBook(page)
  const graph = (await (await page.request.get(`/api/books/${bookId}/graph`)).json()) as {
    nodes: { act_id: string }[]
  }
  await page.request.post(`/api/books/${bookId}/nodes`, {
    data: { act_id: graph.nodes[0]!.act_id, title: 'Forgotten Crypt' },
  })
  await page.goto(`/playtest/${bookId}?view=coverage`)
  await page.getByRole('button', { name: 'Walk the book' }).click()
  const result = page.getByRole('region', { name: 'Coverage result' })
  await expect(result).toContainText('3 of 4', { timeout: 30_000 })
  await expect(result.getByRole('link', { name: 'Forgotten Crypt' })).toBeVisible()
})

test('LLM players play a batch and say where the book confused them', async ({ page }) => {
  const { bookId, start } = await playableBook(page)
  // No text at the start: the offline player says it's confused there.
  await page.request.patch(`/api/nodes/${start}`, { data: { beat_notes: '' } })
  await page.request.post('/api/llm/providers', {
    data: {
      name: `Offline ${rand()}`,
      kind: 'fake',
      models: [{ id: 'offline', input_per_mtok: 1000, output_per_mtok: 1000 }],
    },
  })
  await page.goto(`/playtest/${bookId}`)
  const form = page.getByRole('region', { name: 'New batch' })
  await form.getByRole('radio', { name: 'LLM players' }).click()
  await expect(form.getByLabel('Runs')).toHaveValue('10')
  await form.getByLabel('Runs').fill('3')
  await form.getByLabel('Runs').press('Enter')
  await form.getByLabel('Persona').selectOption('reckless')
  await form.getByLabel('Label').fill('Readers')
  await form.getByLabel('Label').press('Enter')
  await form.getByRole('button', { name: /Run 3 games/ }).click()

  await expect(page.getByRole('heading', { name: 'Readers', exact: true })).toBeVisible({
    timeout: 30_000,
  })
  const confusion = page.getByRole('region', { name: 'Where players got confused' })
  await expect(confusion).toContainText('Start')
  await expect(confusion).toContainText("There's no text here")
  await expect(confusion).toContainText('$')
  await expect(page.getByRole('region', { name: 'Runs', exact: true })).toContainText('Confused')

  await confusion.getByRole('button', { name: /^Replay run 1 \(step 1\)/ }).click()
  const replay = page.getByRole('region', { name: 'Replay of run 1' })
  // Opens at the step the player found confusing.
  await expect(replay.getByText(/Step 0 \//)).toBeVisible()
  const note = replay.getByRole('region', { name: "Player's reasoning" })
  await expect(note).toContainText('Next, the player chose: Fight the orc')
  await expect(note).toContainText('Confused:')
})
