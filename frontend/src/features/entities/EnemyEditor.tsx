import { CircleAlert, FlaskConical, Plus, Trash2, X } from 'lucide-react'
import { useState } from 'react'

import { ApiError } from '@/api/client'
import { useEntities, useRuleSystems } from '@/api/queries'
import type { components } from '@/api/schema'
import { LineChart } from '@/components/charts/LineChart'
import { useVocabulary } from '@/components/gbx/vocabulary'
import { GbxField } from '@/components/gbx/GbxField'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { NumberInput, Select, TextArea, TextInput } from '@/components/ui/inputs'
import { useCombatSweep } from '@/features/mechanics/api'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'
import { EntityArt } from '@/features/art/EntityArt'

import {
  type EnemyUpdate,
  useDeleteEntity,
  useEnemyLevels,
  useSaveEntity,
  useWhereUsed,
} from './api'
import { Panel } from './EntityHeader'
import { ProblemList } from './ProblemList'
import type { Problem } from './problems'
import { ScopeSelect } from './ScopeSelect'
import { WhereUsed } from './WhereUsed'

type Enemy = components['schemas']['EnemyOut']

export function EnemyEditor({
  seriesId,
  enemy,
  problems,
  onDeleted,
}: {
  seriesId: string
  enemy: Enemy
  problems: Problem[] | undefined
  onDeleted: () => void
}) {
  const saveEntity = useSaveEntity('enemies', seriesId)
  const remove = useDeleteEntity('enemies', seriesId)
  const used = useWhereUsed(seriesId, 'enemy', enemy.key)
  const save = (patch: EnemyUpdate | ((cur: Enemy) => EnemyUpdate)) => saveEntity(enemy.id, patch)

  const del = () => {
    const n = used.data?.refs.length ?? 0
    const msg = n
      ? `${enemy.name} is used in ${n} place(s). Delete it anyway? Those references will break.`
      : `Delete ${enemy.name}?`
    if (window.confirm(msg)) remove.mutate({ id: enemy.id, force: n > 0 }, { onSuccess: onDeleted })
  }

  return (
    <div className="space-y-4 pb-10">
      <div className="flex items-center gap-2">
        <h2 className="text-xl font-semibold">{enemy.name}</h2>
        <code className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted">{enemy.key}</code>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto text-danger"
          onClick={del}
          disabled={used.isPending}
        >
          <Trash2 className="size-4" /> Delete
        </Button>
      </div>
      <ProblemList problems={problems} />

      <Panel title="Details">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Field label="Name">
            {(id) => (
              <TextInput
                id={id}
                value={enemy.name}
                onCommit={(name) => name.trim() && save({ name })}
              />
            )}
          </Field>
          <Field label="Key" hint="Used in formulas and tables">
            {(id) => (
              <TextInput
                id={id}
                value={enemy.key}
                onCommit={(key) => key.trim() && save({ key })}
              />
            )}
          </Field>
          <Field label="Available in">
            {(id) => (
              <ScopeSelect
                id={id}
                seriesId={seriesId}
                value={enemy.book_id}
                onChange={(book_id) => save({ book_id })}
              />
            )}
          </Field>
          <Field label="Default level">
            {(id) => (
              <NumberInput
                id={id}
                min={1}
                value={enemy.default_level}
                onCommit={(v) => v && v >= 1 && save({ default_level: v })}
              />
            )}
          </Field>
        </div>
        <Field label="Tags" hint="Comma-separated">
          {(id) => (
            <TextInput
              id={id}
              value={enemy.tags.join(', ')}
              onCommit={(v) =>
                save({
                  tags: v
                    .split(',')
                    .map((t) => t.trim())
                    .filter(Boolean),
                })
              }
            />
          )}
        </Field>
        <Field label="Description">
          {(id) => (
            <TextArea
              id={id}
              rows={2}
              value={enemy.description}
              onCommit={(description) => save({ description })}
            />
          )}
        </Field>
      </Panel>

      <StatsPanel
        enemy={enemy}
        onFormula={(stat, src) =>
          save((cur) => {
            const next = { ...cur.stat_formulas }
            if (src === null) delete next[stat]
            else next[stat] = src
            return { stat_formulas: next }
          })
        }
      />
      <DifficultyPanel seriesId={seriesId} enemy={enemy} />
      <EntityArt seriesId={seriesId} targetType="enemy" targetId={enemy.id} name={enemy.name} />

      <Panel title="Abilities">
        <Rows
          rows={enemy.abilities}
          empty="No special abilities."
          onChange={(f) => save((cur) => ({ abilities: f(cur.abilities) }))}
          blank={{ name: 'New ability', description: '' }}
          addLabel="Add ability"
          render={(a, set) => (
            <>
              <TextInput
                aria-label="Ability name"
                className="w-48"
                value={a.name}
                onCommit={(name) => name.trim() && set({ name })}
              />
              <TextInput
                aria-label="Ability description"
                className="flex-1"
                value={a.description ?? ''}
                onCommit={(description) => set({ description })}
              />
            </>
          )}
        />
      </Panel>

      <LootPanel
        seriesId={seriesId}
        enemy={enemy}
        onChange={(f) => save((cur) => ({ loot: f(cur.loot) }))}
      />

      <Panel title="Where it appears">
        <WhereUsed seriesId={seriesId} targetType="enemy" entityKey={enemy.key} />
      </Panel>
    </div>
  )
}

/** Editable list rows with remove and add. */
export function Rows<T>({
  rows,
  render,
  onChange,
  blank,
  addLabel,
  empty,
  disabled,
}: {
  rows: T[]
  render: (row: T, set: (patch: Partial<T>) => void) => React.ReactNode
  /** Receives a function of the latest rows (never rebuilt from props). */
  onChange: (f: (rows: T[]) => T[]) => void
  blank: T
  addLabel: string
  empty: string
  disabled?: boolean
}) {
  return (
    <div className="space-y-2">
      {rows.length === 0 && <p className="text-sm text-muted">{empty}</p>}
      {rows.map((r, i) => (
        <div key={i} className="flex items-center gap-2">
          {render(r, (patch) =>
            onChange((rs) => rs.map((x, j) => (j === i ? { ...x, ...patch } : x))),
          )}
          <Button
            variant="ghost"
            size="icon"
            aria-label="Remove"
            onClick={() => onChange((rs) => rs.filter((_, j) => j !== i))}
          >
            <X className="size-4" />
          </Button>
        </div>
      ))}
      <Button
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={() => onChange((rs) => [...rs, blank])}
      >
        <Plus className="size-4" /> {addLabel}
      </Button>
    </div>
  )
}

function StatsPanel({
  enemy,
  onFormula,
}: {
  enemy: Enemy
  onFormula: (stat: string, src: string | null) => void
}) {
  const uiTier = useUiStore((s) => s.tier)
  const vocab = useVocabulary()
  const levels = useEnemyLevels(enemy.id, Math.min(50, Math.max(10, enemy.default_level)))
  const [tierPick, setTierPick] = useState<string | null>(null)
  const tiers = levels.data?.tiers ?? []
  const tier =
    tiers.find((t) => t.key === tierPick) ?? tiers.find((t) => t.key === uiTier) ?? tiers[0]

  // Every stat any tier asks enemies for, in tier order, plus stray formulas.
  const stats: { key: string; from: string }[] = []
  for (const t of tiers)
    for (const s of t.stats)
      if (!stats.some((x) => x.key === s)) stats.push({ key: s, from: t.label })
  // Without a level table (no active rules, or still loading) offer every rules stat.
  if (!levels.data)
    for (const s of vocab.stats)
      if (!stats.some((x) => x.key === s.key)) stats.push({ key: s.key, from: s.detail ?? '' })
  for (const s of Object.keys(enemy.stat_formulas))
    if (!stats.some((x) => x.key === s)) stats.push({ key: s, from: '' })

  return (
    <Panel title="Stats by level">
      {levels.isError && <p className="text-sm text-danger">{levels.error.message}</p>}
      <div className="grid gap-3 sm:grid-cols-2">
        {stats.map((s) => (
          <div key={s.key} className="space-y-1">
            <GbxField
              label={`${s.key} formula`}
              context="enemy_formula"
              tier={tier?.key}
              value={enemy.stat_formulas[s.key] ?? null}
              onCommit={(v) => onFormula(s.key, v)}
              placeholder="e.g. 6 + level"
            />
            <p className="text-xs text-muted">
              <span className="font-mono text-text">{s.key}</span>
              {s.from ? ` · needed from ${s.from}` : levels.data ? ' · not used by any tier' : ''}
              {levels.data?.errors[s.key] && (
                <span className="text-danger"> · {levels.data.errors[s.key]}</span>
              )}
            </p>
          </div>
        ))}
      </div>
      {tier && (
        <>
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <div
              role="radiogroup"
              aria-label="Level table tier"
              className="flex rounded-md border border-border bg-bg p-0.5"
            >
              {tiers.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  role="radio"
                  aria-checked={t.key === tier.key}
                  onClick={() => setTierPick(t.key)}
                  className={cn(
                    'rounded px-2.5 py-1 text-xs font-medium',
                    t.key === tier.key ? 'bg-accent text-accent-fg' : 'text-muted hover:text-text',
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {tier.missing.length > 0 && (
              <span className="flex items-center gap-1 text-xs text-warning">
                <CircleAlert className="size-3.5" aria-hidden />
                No formula for {tier.missing.join(', ')} — counts as 0 in {tier.label}
              </span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table
              className="w-full text-sm tabular-nums"
              aria-label={`${tier.label} stats by level`}
            >
              <thead>
                <tr className="text-xs text-muted">
                  <th className="py-1 pr-3 text-left font-medium">Level</th>
                  {tier.stats.map((s) => (
                    <th key={s} className="px-3 py-1 text-right font-medium">
                      {s}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {tier.rows.map((r) => (
                  <tr
                    key={r.level}
                    className={r.level === enemy.default_level ? 'bg-accent/8' : undefined}
                  >
                    <td className="py-1 pr-3">{r.level}</td>
                    {tier.stats.map((s) => (
                      <td
                        key={s}
                        className={cn(
                          'px-3 py-1 text-right',
                          tier.missing.includes(s) && 'text-muted',
                        )}
                      >
                        {r.stats[s] ?? '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
  )
}

function DifficultyPanel({ seriesId, enemy }: { seriesId: string; enemy: Enemy }) {
  const systems = useRuleSystems(seriesId)
  const sweep = useCombatSweep(seriesId)
  const active = systems.data?.find((r) => r.is_active)
  const tiers = (active?.definition.tiers ?? []).slice(0, 3)
  const [results, setResults] = useState<
    { key: string; label: string; points: { x: number; y: number }[] }[]
  >([])
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const formulas = JSON.stringify(enemy.stat_formulas)
  const [ranWith, setRanWith] = useState<string | null>(null)

  const run = async () => {
    setRunning(true)
    setError(null)
    setRanWith(formulas)
    try {
      const out = []
      for (const t of tiers) {
        const r = await sweep.mutateAsync({
          enemy_id: enemy.id,
          tier: t.key,
          level_from: 1,
          level_to: 10,
          runs: 500,
          seed: 1,
        })
        out.push({
          key: t.key,
          label: t.label,
          points: r.points.map((p) => ({ x: p.level, y: p.win_rate })),
        })
      }
      setResults(out)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <Panel
      title="Difficulty vs a reference player"
      aside={
        <Button size="sm" variant="outline" onClick={run} disabled={running || !tiers.length}>
          <FlaskConical className="size-4" />{' '}
          {running ? 'Simulating…' : results.length ? 'Re-run' : 'Simulate'}
        </Button>
      }
    >
      <p className="text-xs text-muted">
        Win rate of a freshly rolled player fighting this enemy alone at levels 1–10, 500 fights per
        level, for up to three tiers.
      </p>
      {error && <p className="text-sm text-danger">{error}</p>}
      {results.length > 0 && ranWith !== formulas && !running && (
        <p role="status" className="text-xs text-warning">
          The formulas changed since this ran — re-run to update the curve.
        </p>
      )}
      {results.length > 0 && (
        <LineChart
          series={results}
          label={`Player win rate against ${enemy.name} by level`}
          xLabel="Enemy level"
        />
      )}
    </Panel>
  )
}

function LootPanel({
  seriesId,
  enemy,
  onChange,
}: {
  seriesId: string
  enemy: Enemy
  onChange: (f: (loot: Enemy['loot']) => Enemy['loot']) => void
}) {
  const items = useEntities('items', seriesId)
  const options = (items.data ?? []).map((i) => ({ value: i.key, label: i.name }))
  return (
    <Panel title="Loot">
      <Rows
        rows={enemy.loot}
        empty="Drops nothing."
        onChange={onChange}
        blank={{ item: options[0]?.value ?? '', qty: 1 }}
        addLabel="Add loot"
        disabled={!options.length}
        render={(l, set) => (
          <>
            <Select
              aria-label="Loot item"
              className="flex-1"
              value={l.item || null}
              placeholder="Choose an item…"
              onValueChange={(item) => item && set({ item })}
              options={
                options.some((o) => o.value === l.item) || !l.item
                  ? options
                  : [...options, { value: l.item, label: `${l.item} (missing)` }]
              }
            />
            <NumberInput
              aria-label="Loot quantity"
              className="w-20"
              min={1}
              value={l.qty ?? 1}
              onCommit={(qty) => qty && qty >= 1 && set({ qty })}
            />
          </>
        )}
      />
    </Panel>
  )
}
