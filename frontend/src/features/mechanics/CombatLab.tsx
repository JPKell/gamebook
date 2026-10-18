import { Dices, FlaskConical, TrendingDown } from 'lucide-react'
import { useState } from 'react'

import { useEntities } from '@/api/queries'
import type { components } from '@/api/schema'
import { Histogram } from '@/components/charts/Histogram'
import { LineChart, type Series } from '@/components/charts/LineChart'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Checkbox, NumberInput, Select } from '@/components/ui/inputs'

import { type LabBody, type LabResult, type SweepResult, useCombatLab, useCombatSweep } from './api'
import type { RuleSystemDef } from './defs'

type TierView = components['schemas']['TierView']
const CUSTOM = '__custom__'

/** Monte Carlo fights against series enemies or ad-hoc stats, plus level sweeps. */
export function CombatLab({
  seriesId,
  ruleSystemId,
  def,
  tier,
  view,
}: {
  seriesId: string
  ruleSystemId: string
  def: RuleSystemDef
  tier: string
  view: TierView
}) {
  const enemies = useEntities('enemies', seriesId)
  const lab = useCombatLab(seriesId)
  const sweep = useCombatSweep(seriesId)
  const enemyStats = view.stats.filter((s) => (s.applies_to ?? []).includes('enemy'))
  const playerStats = view.stats.filter((s) => (s.applies_to ?? ['player']).includes('player'))

  const [enemyId, setEnemyId] = useState<string>(CUSTOM)
  // Defaults come from this tier's own stats, so no stat is silently 0.
  const [custom, setCustom] = useState<Record<string, number>>(() =>
    Object.fromEntries(enemyStats.map((s) => [s.key, s.defeat_at != null ? 8 : 6])),
  )
  const [level, setLevel] = useState(1)
  const [count, setCount] = useState(1)
  const [mode, setMode] = useState<'rolled' | 'fixed'>('rolled')
  const [fixed, setFixed] = useState<Record<string, number>>(() =>
    Object.fromEntries(
      playerStats.map((s) => [s.key, s.kind === 'resource' ? 0 : s.defeat_at != null ? 18 : 9]),
    ),
  )
  const [runs, setRuns] = useState(2000)
  const [seed, setSeed] = useState(1)
  const [levels, setLevels] = useState({ from: 1, to: 10 })
  const [compareTiers, setCompareTiers] = useState(false)
  const [sweeps, setSweeps] = useState<{ tier: string; result: SweepResult }[]>([])
  const [sweepError, setSweepError] = useState<string | null>(null)

  const player = { mode, stats: mode === 'fixed' ? fixed : {} }
  const enemy: LabBody['enemies'][number] =
    enemyId === CUSTOM
      ? { name: 'Custom enemy', stats: custom, count }
      : { enemy_id: enemyId, level, count }

  const run = () =>
    lab.mutate({ rule_system_id: ruleSystemId, tier, enemies: [enemy], player, runs, seed })

  const runSweep = async () => {
    if (enemyId === CUSTOM) return
    setSweepError(null)
    const tiers = compareTiers ? def.tiers.slice(0, 3).map((t) => t.key) : [tier]
    try {
      const results = []
      for (const t of tiers) {
        const result = await sweep.mutateAsync({
          rule_system_id: ruleSystemId,
          tier: t,
          enemy_id: enemyId,
          level_from: levels.from,
          level_to: levels.to,
          count,
          player,
          runs: Math.min(500, Math.floor(30_000 / (levels.to - levels.from + 1))),
          seed,
        })
        results.push({ tier: t, result })
      }
      setSweeps(results)
    } catch (e) {
      setSweepError((e as Error).message)
    }
  }

  const tierLabel = (k: string) => def.tiers.find((t) => t.key === k)?.label ?? k

  return (
    <div className="space-y-5">
      <section
        aria-label="Lab setup"
        className="space-y-4 rounded-xl border border-border bg-surface p-4"
      >
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Field label="Enemy">
            {(id) => (
              <Select
                id={id}
                value={enemyId}
                onValueChange={(v) => v && setEnemyId(v)}
                options={[
                  { value: CUSTOM, label: 'Custom stats' },
                  ...(enemies.data ?? []).map((e) => ({
                    value: e.id,
                    label: e.name,
                    group: 'Series enemies',
                  })),
                ]}
              />
            )}
          </Field>
          {enemyId !== CUSTOM && (
            <Field label="Level">
              {(id) => (
                <NumberInput
                  id={id}
                  min={1}
                  max={100}
                  value={level}
                  onCommit={(v) => setLevel(Math.max(1, Math.min(100, v ?? 1)))}
                />
              )}
            </Field>
          )}
          <Field label="How many">
            {(id) => (
              <NumberInput
                id={id}
                min={1}
                max={10}
                value={count}
                onCommit={(v) => setCount(Math.max(1, Math.min(10, v ?? 1)))}
              />
            )}
          </Field>
          <Field label="Fights">
            {(id) => (
              <Select
                id={id}
                value={String(runs)}
                onValueChange={(v) => v && setRuns(Number(v))}
                options={[500, 2000, 10000].map((n) => ({
                  value: String(n),
                  label: n.toLocaleString(),
                }))}
              />
            )}
          </Field>
        </div>
        {enemyId === CUSTOM && (
          <StatInputs title="Enemy stats" stats={enemyStats} values={custom} onChange={setCustom} />
        )}
        <div className="space-y-2">
          <div role="radiogroup" aria-label="Player" className="flex gap-4 text-sm">
            <span className="text-xs font-medium text-muted">Player</span>
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="player-mode"
                checked={mode === 'rolled'}
                onChange={() => setMode('rolled')}
              />
              Rolled each fight
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="player-mode"
                checked={mode === 'fixed'}
                onChange={() => setMode('fixed')}
              />
              Fixed stats
            </label>
          </div>
          {mode === 'fixed' && (
            <StatInputs
              title="Player stats"
              stats={playerStats}
              values={fixed}
              onChange={setFixed}
            />
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={run} disabled={lab.isPending}>
            <FlaskConical className="size-4" />{' '}
            {lab.isPending ? 'Simulating…' : `Run ${runs.toLocaleString()} fights`}
          </Button>
          <label className="flex items-center gap-1.5 text-xs text-muted">
            Seed
            <NumberInput
              aria-label="Seed"
              min={0}
              value={seed}
              onCommit={(v) => setSeed(Math.max(0, v ?? 0))}
              className="w-24 py-1"
            />
          </label>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSeed(Math.floor(Math.random() * 1_000_000))}
            title="Same seed, same results"
          >
            <Dices className="size-4" /> New seed
          </Button>
        </div>
      </section>

      {lab.data && <LabResults result={lab.data} tierLabel={tierLabel(tier)} />}

      <section
        aria-label="Difficulty curve"
        className="space-y-3 rounded-xl border border-border bg-surface p-4"
      >
        <h3 className="flex items-center gap-2 font-semibold">
          <TrendingDown className="size-4 text-muted" aria-hidden /> Difficulty curve
        </h3>
        {enemyId === CUSTOM ? (
          <p className="text-sm text-muted">
            Choose a series enemy above: the curve uses its stat formulas at each level.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Levels from">
                {(id) => (
                  <NumberInput
                    id={id}
                    min={1}
                    max={100}
                    value={levels.from}
                    onCommit={(v) => setLevels((l) => ({ ...l, from: Math.max(1, v ?? 1) }))}
                    className="w-20"
                  />
                )}
              </Field>
              <Field label="to">
                {(id) => (
                  <NumberInput
                    id={id}
                    min={1}
                    max={100}
                    value={levels.to}
                    onCommit={(v) =>
                      setLevels((l) => ({ ...l, to: Math.min(100, Math.max(l.from, v ?? l.from)) }))
                    }
                    className="w-20"
                  />
                )}
              </Field>
              <Checkbox
                label={`Compare tiers (${def.tiers
                  .slice(0, 3)
                  .map((t) => t.label)
                  .join(', ')})`}
                checked={compareTiers}
                onCheckedChange={setCompareTiers}
              />
              <Button variant="outline" onClick={() => void runSweep()} disabled={sweep.isPending}>
                {sweep.isPending ? 'Simulating…' : 'Plot win rate by level'}
              </Button>
            </div>
            {sweepError && <p className="text-sm text-danger">{sweepError}</p>}
            {sweeps.length > 0 && <SweepChart sweeps={sweeps} tierLabel={tierLabel} />}
          </>
        )}
      </section>
    </div>
  )
}

function StatInputs({
  title,
  stats,
  values,
  onChange,
}: {
  title: string
  stats: { key: string; label: string }[]
  values: Record<string, number>
  onChange: (v: Record<string, number>) => void
}) {
  return (
    <fieldset>
      <legend className="mb-1 text-xs font-medium text-muted">{title}</legend>
      <div className="flex flex-wrap gap-3">
        {stats.map((s) => (
          <label key={s.key} className="flex items-center gap-1.5 text-sm">
            <span className="font-mono text-xs">{s.key}</span>
            <NumberInput
              aria-label={`${title}: ${s.label}`}
              value={values[s.key] ?? 0}
              onCommit={(v) => onChange({ ...values, [s.key]: v ?? 0 })}
              className="w-20 py-1"
            />
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  )
}

function LabResults({ result, tierLabel }: { result: LabResult; tierLabel: string }) {
  const pct = (v: number) => `${Math.round(v * 1000) / 10}%`
  const foes = result.enemies
    .map(
      (e) =>
        `${e.count > 1 ? `${e.count}× ` : ''}${e.name} (${Object.entries(e.stats)
          .map(([k, v]) => `${k} ${v}`)
          .join(', ')})`,
    )
    .join(' + ')
  return (
    <section aria-label="Lab results" className="space-y-4">
      <p className="text-sm text-muted">
        {tierLabel} tier · {result.runs.toLocaleString()} fights against {foes}
      </p>
      {result.truncated && (
        <p
          role="status"
          className="rounded-md border border-warning/40 bg-warning/8 px-3 py-2 text-sm"
        >
          These fights run very long, so the lab stopped after {result.runs.toLocaleString()} to
          stay responsive.
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          label="Player wins"
          value={pct(result.win_rate)}
          sub={`${result.losses.toLocaleString()} losses${result.stalemates ? ` · ${result.stalemates} stalemates` : ''}`}
        />
        <Tile
          label="Rounds per fight"
          value={result.rounds.mean.toFixed(1)}
          sub={`90% within ${result.rounds.p90}`}
        />
        <Tile
          label={`${result.damage_stat} lost`}
          value={result.damage_taken.mean.toFixed(1)}
          sub={`90% lose ≤ ${result.damage_taken.p90}`}
        />
        <Tile
          label={`${result.damage_stat} left after a win`}
          value={result.remaining_on_win_mean.toFixed(1)}
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <figure className="rounded-xl border border-border bg-surface p-4">
          <figcaption className="mb-2 text-sm font-medium">Rounds per fight</figcaption>
          <Histogram
            data={result.rounds.histogram}
            label="Rounds per fight histogram"
            valueLabel={(v) => `${v} round${v === 1 ? '' : 's'}`}
          />
          <TableView rows={result.rounds.histogram} heading="Rounds" total={result.runs} />
        </figure>
        <figure className="rounded-xl border border-border bg-surface p-4">
          <figcaption className="mb-2 text-sm font-medium">
            {result.damage_stat} lost per fight
          </figcaption>
          <Histogram
            data={result.damage_taken.histogram}
            label={`${result.damage_stat} lost histogram`}
            valueLabel={(v) => `${v} ${result.damage_stat} lost`}
          />
          <TableView
            rows={result.damage_taken.histogram}
            heading={`${result.damage_stat} lost`}
            total={result.runs}
          />
        </figure>
      </div>
    </section>
  )
}

function TableView({
  rows,
  heading,
  total,
}: {
  rows: Record<string, number>
  heading: string
  total: number
}) {
  return (
    <details className="mt-2 text-xs">
      <summary className="cursor-pointer text-muted">Table view</summary>
      <table className="mt-2 w-full text-left">
        <thead className="text-muted">
          <tr>
            <th className="py-1 font-medium">{heading}</th>
            <th className="py-1 font-medium">Fights</th>
            <th className="py-1 font-medium">Share</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(rows).map(([k, v]) => (
            <tr key={k} className="border-t border-border">
              <td className="py-0.5">{k}</td>
              <td className="py-0.5">{v}</td>
              <td className="py-0.5">{((v / total) * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}

function SweepChart({
  sweeps,
  tierLabel,
}: {
  sweeps: { tier: string; result: SweepResult }[]
  tierLabel: (k: string) => string
}) {
  const series: Series[] = sweeps.map(({ tier, result }) => ({
    key: tier,
    label: tierLabel(tier),
    points: result.points.map((p) => ({ x: p.level, y: p.win_rate })),
  }))
  const name = sweeps[0]?.result.name ?? 'enemy'
  return (
    <figure>
      <figcaption className="mb-2 text-sm font-medium">
        Player win rate against {name}, by enemy level
      </figcaption>
      <LineChart series={series} label={`Win rate against ${name} by level`} xLabel="Level" />
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer text-muted">Table view</summary>
        <table className="mt-2 w-full text-left">
          <thead className="text-muted">
            <tr>
              <th className="py-1 font-medium">Level</th>
              {sweeps.map((s) => (
                <th key={s.tier} className="py-1 font-medium">
                  {tierLabel(s.tier)}
                </th>
              ))}
              <th className="py-1 font-medium">
                Enemy stats ({tierLabel(sweeps[sweeps.length - 1]!.tier)})
              </th>
            </tr>
          </thead>
          <tbody>
            {sweeps[0]!.result.points.map((p, i) => (
              <tr key={p.level} className="border-t border-border">
                <td className="py-0.5">{p.level}</td>
                {sweeps.map((s) => (
                  <td key={s.tier} className="py-0.5">
                    {Math.round((s.result.points[i]?.win_rate ?? 0) * 100)}%
                  </td>
                ))}
                <td className="py-0.5 font-mono">
                  {Object.entries(sweeps[sweeps.length - 1]!.result.points[i]?.enemy ?? {})
                    .map(([k, v]) => `${k} ${v}`)
                    .join(' · ')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  )
}
