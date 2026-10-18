import { expect, type Page, test } from '@playwright/test'

const rand = () => Math.random().toString(36).slice(2, 7)

/** A series + book whose start section has beat notes and two choices. */
async function book(page: Page) {
  const r = page.request
  const series = (await (
    await r.post('/api/series', { data: { title: `Prose ${rand()}` } })
  ).json()) as {
    id: string
  }
  const b = (await (
    await r.post(`/api/series/${series.id}/books`, { data: { title: `Book ${rand()}` } })
  ).json()) as { id: string; start_node_id: string }
  await r.patch(`/api/nodes/${b.start_node_id}`, {
    data: { beat_notes: 'A raven lands on the iron gate. The road forks.' },
  })
  const g = (await (await r.get(`/api/books/${b.id}/graph`)).json()) as {
    nodes: { act_id: string }[]
  }
  for (const title of ['Left road', 'Right road']) {
    await r.post(`/api/books/${b.id}/nodes`, {
      data: {
        act_id: g.nodes[0]!.act_id,
        title,
        link_from: { node_id: b.start_node_id, label: `Take the ${title.toLowerCase()}` },
      },
    })
  }
  return { seriesId: series.id, bookId: b.id, start: b.start_node_id }
}

async function offlineProvider(page: Page) {
  const res = await page.request.post('/api/llm/providers', {
    data: {
      name: `Offline ${rand()}`,
      kind: 'fake',
      models: [{ id: 'offline', input_per_mtok: 1, output_per_mtok: 2 }],
    },
  })
  return (await res.json()) as { id: string; name: string }
}

test('settings: providers and versioned prompt templates', async ({ page }) => {
  await page.goto('/settings')
  await page.getByRole('button', { name: /Offline test model/ }).click()
  const card = page.getByRole('region', { name: 'Offline test model' }).first()
  await card.getByRole('button', { name: 'Test connection' }).click()
  await expect(card.getByRole('status')).toContainText('Connected')

  await page.getByRole('radio', { name: 'Prompt templates' }).click()
  await page.getByRole('tab', { name: 'Critic' }).click()
  const system = page.getByLabel('System prompt')
  await expect(system).toHaveValue(/demanding gamebook editor/)
  await system.fill('Be a kind critic. Reply with JSON.')
  await page.getByRole('button', { name: /Save as version/ }).click()
  await expect(page.getByText(/^v\d+$/).first()).toBeVisible()
  await expect(system).toHaveValue('Be a kind critic. Reply with JSON.')
  // Back to the built-in version (other tests rely on the default critic).
  const v1 = page.getByRole('listitem').filter({ hasText: 'v1' })
  await v1.getByRole('button', { name: 'Use' }).click()
  await expect(system).toHaveValue(/demanding gamebook editor/)
})

test('generate, review the critique, approve with edits, see it in the player and go stale', async ({
  page,
}) => {
  const { bookId, start } = await book(page)
  const provider = await offlineProvider(page)
  await page.goto(`/writing/${bookId}`)

  await page.getByRole('button', { name: 'Pipeline settings' }).click()
  await page.getByLabel('Writer provider').selectOption({ label: provider.name })
  await page.getByLabel('Writer model').selectOption('offline')
  await page.getByRole('button', { name: 'Save' }).click()

  await page
    .getByRole('button', { name: /^Start/ })
    .first()
    .click()
  await expect(page.getByRole('region', { name: 'Context' })).toContainText(
    'A raven lands on the iron gate.',
  )
  await expect(page.getByRole('region', { name: 'Context' })).toContainText('Take the left road')
  await page.getByLabel('Notes for the writer').fill('Make it eerie.')
  await page.getByRole('button', { name: 'Generate' }).click()

  const draft = page.getByRole('region', { name: 'Draft' })
  await expect(draft.getByLabel('Prose')).toHaveValue(/raven lands on the iron gate/, {
    timeout: 20_000,
  })
  const critique = page.getByRole('complementary', { name: 'Critique' })
  await expect(critique).toContainText('Pass 1: 6.0 / 10')
  await expect(critique).toContainText('Pass 2: 8.0 / 10')
  await expect(critique).toContainText('Make it eerie.')

  await draft.getByLabel('Prose').fill('A raven watches from the gate. Two roads wait.')
  await draft.getByRole('button', { name: 'Approve with my edits' }).click()
  await expect(page.getByRole('button', { name: /^Start/ }).first()).toContainText('Approved')
  await draft.getByRole('button', { name: 'Changes since previous' }).click()
  await expect(draft.getByLabel('Changes').locator('ins').first()).toBeVisible()

  await page.goto(`/playtest/${bookId}?view=play`)
  await expect(page.getByRole('region', { name: 'Prose' })).toContainText(
    'A raven watches from the gate.',
  )

  await page.request.patch(`/api/nodes/${start}`, { data: { beat_notes: 'A crow, not a raven.' } })
  await page.goto(`/writing/${bookId}`)
  await expect(page.getByRole('button', { name: /^Start/ }).first()).toContainText('Stale')
  await page.goto(`/story/${bookId}?node=${start}`)
  await expect(page.getByRole('group', { name: 'Prose' })).toContainText('Stale')
})

test('write a whole act in canonical order', async ({ page }) => {
  const { bookId, seriesId } = await book(page)
  const provider = await offlineProvider(page)
  await page.request.put(`/api/series/${seriesId}/writing-settings`, {
    data: { roles: { writer: { provider_id: provider.id, model: 'offline' } } },
  })
  await page.goto(`/writing/${bookId}`)
  await page.getByRole('button', { name: 'Write an act' }).click()
  await page.getByRole('button', { name: 'Start' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Wrote 3 sections' })).toBeVisible({
    timeout: 30_000,
  })
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: /In review 3/ }).click()
  await expect(
    page.getByRole('complementary', { name: 'Writing queue' }).getByRole('listitem'),
  ).toHaveCount(3)
})
