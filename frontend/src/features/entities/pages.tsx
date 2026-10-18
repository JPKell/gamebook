import { Dices, Gem, Skull } from 'lucide-react'
import { useParams, useSearchParams } from 'react-router'

import { useEntities } from '@/api/queries'
import { VocabularyContext } from '@/components/gbx/vocabulary'
import { EmptyState } from '@/components/ui/empty'
import { cn } from '@/lib/utils'

import { useCreateEntity, useItemTotals } from './api'
import { EnemyEditor } from './EnemyEditor'
import { EntityHeader } from './EntityHeader'
import { CATEGORIES } from './categories'
import { ItemEditor } from './ItemEditor'
import { MasterDetail } from './MasterDetail'
import { counts, useProblemsById } from './problems'
import { SeriesRedirect } from './SeriesRedirect'
import { TableEditor } from './TableEditor'
import { useSeriesVocab } from './useSeriesVocab'

export const EnemiesIndex = () => <SeriesRedirect base="/enemies" icon={Skull} what="Enemies" />
export const ItemsIndex = () => <SeriesRedirect base="/items" icon={Gem} what="Items" />

/** The selected entity lives in ?id= so it survives reloads and can be linked. */
function useSelection() {
  const [params, setParams] = useSearchParams()
  const set = (patch: Record<string, string | null>) =>
    setParams(
      (p) => {
        for (const [k, v] of Object.entries(patch)) {
          if (v === null) p.delete(k)
          else p.set(k, v)
        }
        return p
      },
      { replace: true },
    )
  return { params, set }
}

export function EnemiesPage() {
  const { seriesId = '' } = useParams()
  const { params, set } = useSelection()
  const vocab = useSeriesVocab(seriesId)
  const tab = params.get('tab') === 'tables' ? 'tables' : 'enemies'
  const enemies = useEntities('enemies', seriesId)
  const tables = useEntities('tables', seriesId)
  const problems = useProblemsById(seriesId)
  const createEnemy = useCreateEntity('enemies', seriesId)
  const createTable = useCreateEntity('tables', seriesId)
  const id = params.get('id')
  const enemy = enemies.data?.find((e) => e.id === id)
  const table = tables.data?.find((t) => t.id === id)

  return (
    <VocabularyContext.Provider value={vocab}>
      <div className="mx-auto flex h-full max-w-7xl flex-col gap-4 px-6 py-6">
        <EntityHeader title="Enemies" base="/enemies" seriesId={seriesId}>
          <div
            role="radiogroup"
            aria-label="Enemies view"
            className="ml-auto flex rounded-md border border-border bg-bg p-0.5"
          >
            {(
              [
                ['enemies', 'Enemies', Skull],
                ['tables', 'Random tables', Dices],
              ] as const
            ).map(([v, label, Icon]) => (
              <button
                key={v}
                type="button"
                role="radio"
                aria-checked={tab === v}
                onClick={() => set({ tab: v === 'enemies' ? null : v, id: null })}
                className={cn(
                  'flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium',
                  tab === v ? 'bg-accent text-accent-fg' : 'text-muted hover:text-text',
                )}
              >
                <Icon className="size-3.5" aria-hidden /> {label}
              </button>
            ))}
          </div>
        </EntityHeader>
        {tab === 'enemies' ? (
          <MasterDetail
            label="Enemies"
            loading={enemies.isPending}
            createLabel="New enemy"
            rows={(enemies.data ?? []).map((e) => ({
              id: e.id,
              title: e.name,
              subtitle: [`level ${e.default_level}`, ...e.tags].join(' · '),
              ...counts(problems.get(e.id)),
            }))}
            selectedId={enemy ? enemy.id : null}
            onSelect={(v) => set({ id: v })}
            onCreate={(name) =>
              createEnemy.mutate({ name }, { onSuccess: (e) => set({ id: e.id }) })
            }
            detail={
              enemy && (
                <EnemyEditor
                  key={enemy.id}
                  seriesId={seriesId}
                  enemy={enemy}
                  problems={problems.get(enemy.id)}
                  onDeleted={() => set({ id: null })}
                />
              )
            }
            empty={
              <EmptyState icon={Skull} title="Pick an enemy">
                Enemies have a stat formula per tier, so one goblin scales from level 1 to 10 and
                from Basic to Advanced rules.
              </EmptyState>
            }
          />
        ) : (
          <MasterDetail
            label="Random tables"
            loading={tables.isPending}
            createLabel="New table"
            rows={(tables.data ?? []).map((t) => ({
              id: t.id,
              title: t.name,
              subtitle: `${t.dice} · ${t.entries.length} result${t.entries.length === 1 ? '' : 's'}`,
              ...counts(problems.get(t.id)),
            }))}
            selectedId={table ? table.id : null}
            onSelect={(v) => set({ id: v })}
            onCreate={(name) =>
              createTable.mutate({ name }, { onSuccess: (t) => set({ id: t.id }) })
            }
            detail={
              table && (
                <TableEditor
                  key={table.id}
                  seriesId={seriesId}
                  table={table}
                  problems={problems.get(table.id)}
                  onDeleted={() => set({ id: null })}
                />
              )
            }
            empty={
              <EmptyState icon={Dices} title="Pick a table">
                Random tables turn a dice roll into an encounter, an item, some gold or nothing at
                all.
              </EmptyState>
            }
          />
        )}
      </div>
    </VocabularyContext.Provider>
  )
}

export function ItemsPage() {
  const { seriesId = '' } = useParams()
  const { params, set } = useSelection()
  const vocab = useSeriesVocab(seriesId)
  const items = useEntities('items', seriesId)
  const totals = useItemTotals(seriesId)
  const problems = useProblemsById(seriesId)
  const create = useCreateEntity('items', seriesId)
  const item = items.data?.find((i) => i.id === params.get('id'))
  const order = CATEGORIES.map((c) => c.value as string)
  const rank = (c: string) => (order.includes(c) ? order.indexOf(c) : order.length)
  const sorted = [...(items.data ?? [])].sort(
    (a, b) => rank(a.category) - rank(b.category) || a.name.localeCompare(b.name),
  )

  return (
    <VocabularyContext.Provider value={vocab}>
      <div className="mx-auto flex h-full max-w-7xl flex-col gap-4 px-6 py-6">
        <EntityHeader title="Items" base="/items" seriesId={seriesId} />
        <MasterDetail
          label="Items"
          loading={items.isPending}
          createLabel="New item"
          rows={sorted.map((i) => {
            const t = totals.data?.[i.key]
            return {
              id: i.id,
              title: i.name,
              subtitle: i.slot ?? undefined,
              group: CATEGORIES.find((c) => c.value === i.category)?.label ?? i.category,
              aside: (
                <span
                  className="shrink-0 text-xs text-muted tabular-nums"
                  title={`${t?.total ?? 0} in the game${t?.unlimited ? ' plus unlimited shop stock' : ''}, ${t?.uses ?? 0} uses`}
                >
                  ×{t?.total ?? 0}
                  {t?.unlimited && '+'}
                </span>
              ),
              ...counts(problems.get(i.id)),
            }
          })}
          selectedId={item ? item.id : null}
          onSelect={(v) => set({ id: v })}
          onCreate={(name) => create.mutate({ name }, { onSuccess: (i) => set({ id: i.id }) })}
          detail={
            item && (
              <ItemEditor
                key={item.id}
                seriesId={seriesId}
                item={item}
                problems={problems.get(item.id)}
                onDeleted={() => set({ id: null })}
              />
            )
          }
          empty={
            <EmptyState icon={Gem} title="Pick an item">
              Quantities are counted from where items are placed, sold, given and dropped across
              every book.
            </EmptyState>
          }
        />
      </div>
    </VocabularyContext.Provider>
  )
}
