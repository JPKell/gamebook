/** Shape of a batch summary (backend: core/sim/batch.py `summarize`). */
export interface Summary {
  runs: number
  win_rate: number
  outcomes: Record<string, number>
  endings: Record<string, number>
  steps: { mean: number; p50: number; p90: number; max: number }
  node_visits: Record<string, number>
  deaths_by_node: Record<string, number>
  death_causes: Record<string, number>
  acts: { act_id: string; title: string; reached: number }[]
  enemies: Record<string, { fights: number; losses: number; deaths: number }>
  items: Record<string, { held_runs: number; wins_with: number; lift: number | null }>
  coverage: {
    nodes_total: number
    nodes_visited: number
    unvisited: string[]
    endings_total: number
    endings_reached: number
    choices_total: number
    choices_taken: number
  }
  errors: { runs: number; sample: string[] }
  /** LLM batches only. */
  llm?: {
    steps: number
    confused_steps: number
    cost_usd: number
    stopped_runs: number
    failed_runs?: number
    confusion: {
      node_id: string | null
      count: number
      notes: { run: number; step: number; text: string }[]
    }[]
  }
}

export const DEATHS = ['death', 'defeated']

export const OUTCOME_LABELS: Record<string, string> = {
  victory: 'Victory',
  death: 'Death (ending)',
  defeated: 'Defeated',
  dead_end: 'Dead end',
  stuck: 'Stuck',
  max_steps: 'Ran out of steps',
  error: 'Error',
  stopped: 'Stopped (budget or cancel)',
  llm_error: 'Model error',
}

export const usd = (x: number) => (x < 0.01 && x > 0 ? `$${x.toFixed(4)}` : `$${x.toFixed(2)}`)

export const pct = (x: number, digits = 1) => `${(x * 100).toFixed(digits)}%`

export const deathRate = (s: Summary) =>
  s.runs ? DEATHS.reduce((n, k) => n + (s.outcomes[k] ?? 0), 0) / s.runs : 0

export const coverageRate = (s: Summary) =>
  s.coverage.nodes_total ? s.coverage.nodes_visited / s.coverage.nodes_total : 0

/** Headline metrics shared by the dashboard tiles and batch comparison. */
export const METRICS: {
  key: string
  label: string
  get: (s: Summary) => number
  fmt: (v: number) => string
  better: 'up' | 'down' | null
}[] = [
  { key: 'win', label: 'Win rate', get: (s) => s.win_rate, fmt: (v) => pct(v), better: null },
  { key: 'death', label: 'Death rate', get: deathRate, fmt: (v) => pct(v), better: null },
  {
    key: 'steps',
    label: 'Median steps',
    get: (s) => s.steps.p50,
    fmt: (v) => String(v),
    better: null,
  },
  {
    key: 'steps90',
    label: '90th percentile steps',
    get: (s) => s.steps.p90,
    fmt: (v) => String(v),
    better: null,
  },
  {
    key: 'coverage',
    label: 'Nodes visited',
    get: coverageRate,
    fmt: (v) => pct(v, 0),
    better: 'up',
  },
  {
    key: 'endings',
    label: 'Endings reached',
    get: (s) => s.coverage.endings_reached,
    fmt: (v) => String(v),
    better: 'up',
  },
  {
    key: 'errors',
    label: 'Runs with errors',
    get: (s) => s.errors.runs,
    fmt: (v) => String(v),
    better: 'down',
  },
]
