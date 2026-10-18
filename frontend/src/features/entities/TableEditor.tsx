import { useQuery } from '@tanstack/react-query'
import { CircleAlert, CircleCheck, Plus, Trash2, X } from 'lucide-react'

import { api, unwrap } from '@/api/client'
import { useEntities } from '@/api/queries'
import type { components } from '@/api/schema'
import { GbxField } from '@/components/gbx/GbxField'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { NumberInput, Select, TextArea, TextInput } from '@/components/ui/inputs'

import { type TableUpdate, useDeleteEntity, useSaveEntity, useWhereUsed } from './api'
import { coverage, fmtRanges } from './coverage'
import { Panel } from './EntityHeader'
import { ProblemList } from './ProblemList'
import type { Problem } from './problems'
import { ScopeSelect } from './ScopeSelect'
import { WhereUsed } from './WhereUsed'

type Table = components['schemas']['TableOut']
type Entry = components['schemas']['TableEntryIn']
type Kind = NonNullable<Entry['kind']>

const KINDS: { value: Kind; label: string }[] = [
  { value: 'enemies', label: 'Enemies' },
  { value: 'item', label: 'Item' },
  { value: 'gold', label: 'Gold' },
  { value: 'nothing', label: 'Nothing' },
]

function useDice(seriesId: string, dice: string) {
  return useQuery({
    queryKey: ['gbx-dice', seriesId, dice],
    queryFn: () =>
      unwrap(
        api.POST('/api/gbx/check', {
          body: { source: dice, context: 'roll', series_id: seriesId },
        }),
      ),
    enabled: !!dice.trim(),
    staleTime: Infinity,
  })
}

const pct = (p: number) => `${(p * 100).toFixed(p < 0.1 ? 1 : 0)}%`

export function TableEditor({
  seriesId,
  table,
  problems,
  onDeleted,
}: {
  seriesId: string
  table: Table
  problems: Problem[] | undefined
  onDeleted: () => void
}) {
  const saveEntity = useSaveEntity('tables', seriesId)
  const remove = useDeleteEntity('tables', seriesId)
  const used = useWhereUsed(seriesId, 'table', table.key)
  const enemies = useEntities('enemies', seriesId)
  const items = useEntities('items', seriesId)
  const dice = useDice(seriesId, table.dice)
  const save = (patch: TableUpdate) => saveEntity(table.id, patch)
  const entries = table.entries
  // Every list edit is a function of the latest entries, never of render-time props.
  const editEntries = (f: (es: Entry[]) => Entry[]) =>
    saveEntity(table.id, (cur) => ({ entries: f(cur.entries) }))
  const setEntry = (i: number, patch: Partial<Entry> | ((e: Entry) => Partial<Entry>)) =>
    editEntries((es) =>
      es.map((e, j) =>
        j === i ? { ...e, ...(typeof patch === 'function' ? patch(e) : patch) } : e,
      ),
    )
  type Foe = NonNullable<Entry['enemies']>[number]
  const editFoes = (i: number, f: (foes: Foe[]) => Foe[]) =>
    setEntry(i, (e) => ({ enemies: f(e.enemies ?? []) }))
  const setFoe = (i: number, k: number, patch: Partial<Foe>) =>
    editFoes(i, (fs) => fs.map((y, m) => (m === k ? { ...y, ...patch } : y)))

  const cov = coverage(entries, dice.data?.range ?? null, dice.data?.distribution ?? null)
  const range = dice.data?.range
  const enemyOptions = (enemies.data ?? []).map((e) => ({ value: e.key, label: e.name }))
  const itemOptions = (items.data ?? []).map((i) => ({ value: i.key, label: i.name }))

  // New rows start at the first uncovered roll, or after the last row.
  const addEntry = () =>
    editEntries((es) => {
      const lo =
        cov.gaps[0]?.lo ?? es.reduce((m, e) => Math.max(m, e.hi), (range?.[0] ?? 1) - 1) + 1
      return [...es, { lo, hi: lo, kind: 'nothing', enemies: [], qty: 1, note: '' }]
    })

  const del = () => {
    const n = used.data?.refs.length ?? 0
    const msg = n
      ? `${table.name} is used in ${n} place(s). Delete it anyway?`
      : `Delete ${table.name}?`
    if (window.confirm(msg)) remove.mutate({ id: table.id, force: n > 0 }, { onSuccess: onDeleted })
  }

  return (
    <div className="space-y-4 pb-10">
      <div className="flex items-center gap-2">
        <h2 className="text-xl font-semibold">{table.name}</h2>
        <code className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted">{table.key}</code>
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
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          <Field label="Name">
            {(id) => (
              <TextInput
                id={id}
                value={table.name}
                onCommit={(name) => name.trim() && save({ name })}
              />
            )}
          </Field>
          <Field label="Key">
            {(id) => (
              <TextInput
                id={id}
                value={table.key}
                onCommit={(key) => key.trim() && save({ key })}
              />
            )}
          </Field>
          <Field label="Available in">
            {(id) => (
              <ScopeSelect
                id={id}
                seriesId={seriesId}
                value={table.book_id}
                onChange={(book_id) => save({ book_id })}
              />
            )}
          </Field>
        </div>
        <Field label="Description">
          {(id) => (
            <TextArea
              id={id}
              rows={2}
              value={table.description}
              onCommit={(description) => save({ description })}
            />
          )}
        </Field>
      </Panel>

      <Panel
        title="Results"
        aside={
          range && (
            <span className="text-xs text-muted">
              Rolls {range[0]}–{range[1]}
            </span>
          )
        }
      >
        <div className="max-w-xs">
          <GbxField
            label="Dice"
            context="roll"
            value={table.dice}
            onCommit={(v) => v && save({ dice: v })}
            placeholder="e.g. 2d6"
          />
        </div>
        {range &&
          (cov.gaps.length || cov.overlaps.length ? (
            <div role="status" className="space-y-1 text-sm text-warning">
              {cov.gaps.length > 0 && (
                <p className="flex items-center gap-1.5">
                  <CircleAlert className="size-4" aria-hidden /> Nothing happens on{' '}
                  {fmtRanges(cov.gaps)}
                </p>
              )}
              {cov.overlaps.length > 0 && (
                <p className="flex items-center gap-1.5">
                  <CircleAlert className="size-4" aria-hidden /> Several results share{' '}
                  {fmtRanges(cov.overlaps)} — the first one wins
                </p>
              )}
            </div>
          ) : (
            entries.length > 0 && (
              <p role="status" className="flex items-center gap-1.5 text-sm text-success">
                <CircleCheck className="size-4" aria-hidden /> Every roll has exactly one result
              </p>
            )
          ))}
        <div className="space-y-2">
          {entries.length === 0 && <p className="text-sm text-muted">No results yet.</p>}
          {entries.map((e, i) => (
            <div
              key={i}
              className="space-y-2 rounded-lg border border-border p-2"
              aria-label={`Result ${i + 1}`}
              role="group"
            >
              <div className="flex flex-wrap items-center gap-2">
                <NumberInput
                  aria-label="From"
                  className="w-16"
                  value={e.lo}
                  onCommit={(lo) =>
                    lo !== null && setEntry(i, (cur) => ({ lo, hi: Math.max(lo, cur.hi) }))
                  }
                />
                <span className="text-muted">–</span>
                <NumberInput
                  aria-label="To"
                  className="w-16"
                  value={e.hi}
                  onCommit={(hi) =>
                    hi !== null && setEntry(i, (cur) => ({ hi, lo: Math.min(hi, cur.lo) }))
                  }
                />
                <Select
                  aria-label="Result kind"
                  className="w-32"
                  value={e.kind ?? 'nothing'}
                  options={KINDS}
                  onValueChange={(kind) => kind && setEntry(i, { kind })}
                />
                {e.kind === 'item' && (
                  <>
                    <Select
                      aria-label="Item"
                      className="w-44"
                      value={e.item ?? null}
                      placeholder="Choose…"
                      options={itemOptions}
                      onValueChange={(item) => setEntry(i, { item })}
                    />
                    <NumberInput
                      aria-label="Quantity"
                      className="w-16"
                      min={1}
                      value={e.qty ?? 1}
                      onCommit={(qty) => qty && qty >= 1 && setEntry(i, { qty })}
                    />
                  </>
                )}
                {e.kind === 'gold' && (
                  <div className="w-40">
                    <GbxField
                      label="Gold amount"
                      context="amount"
                      value={e.amount ?? null}
                      onCommit={(amount) => setEntry(i, { amount })}
                      placeholder="e.g. 1d6"
                    />
                  </div>
                )}
                <TextInput
                  aria-label="Note"
                  placeholder="Note"
                  className="min-w-32 flex-1"
                  value={e.note ?? ''}
                  onCommit={(note) => setEntry(i, { note })}
                />
                <span
                  className="w-12 text-right text-xs text-muted tabular-nums"
                  title="Chance of this result"
                >
                  {cov.chances[i] != null ? pct(cov.chances[i]!) : ''}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Remove result"
                  onClick={() => editEntries((es) => es.filter((_, j) => j !== i))}
                >
                  <X className="size-4" />
                </Button>
              </div>
              {e.kind === 'enemies' && (
                <div className="space-y-1 pl-4">
                  {(e.enemies ?? []).map((x, k) => (
                    <div key={k} className="flex items-center gap-2">
                      <Select
                        aria-label="Enemy"
                        className="w-48"
                        value={x.enemy}
                        options={
                          enemyOptions.some((o) => o.value === x.enemy)
                            ? enemyOptions
                            : [...enemyOptions, { value: x.enemy, label: `${x.enemy} (missing)` }]
                        }
                        onValueChange={(enemy) => enemy && setFoe(i, k, { enemy })}
                      />
                      <span className="text-xs text-muted">level</span>
                      <NumberInput
                        aria-label="Enemy level"
                        className="w-16"
                        min={1}
                        value={x.level ?? 1}
                        onCommit={(level) => level && level >= 1 && setFoe(i, k, { level })}
                      />
                      <span className="text-xs text-muted">×</span>
                      <NumberInput
                        aria-label="Enemy count"
                        className="w-16"
                        min={1}
                        value={x.count ?? 1}
                        onCommit={(count) => count && count >= 1 && setFoe(i, k, { count })}
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Remove enemy"
                        onClick={() => editFoes(i, (fs) => fs.filter((_, m) => m !== k))}
                      >
                        <X className="size-4" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={!enemyOptions.length}
                    onClick={() =>
                      editFoes(i, (fs) => [
                        ...fs,
                        { enemy: enemyOptions[0]!.value, level: 1, count: 1 },
                      ])
                    }
                  >
                    <Plus className="size-4" /> Add enemy
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
        <Button variant="outline" size="sm" onClick={addEntry}>
          <Plus className="size-4" /> Add result
        </Button>
      </Panel>

      <Panel title="Where it's rolled">
        <WhereUsed seriesId={seriesId} targetType="table" entityKey={table.key} />
      </Panel>
    </div>
  )
}
