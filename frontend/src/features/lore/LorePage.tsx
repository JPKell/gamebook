import { BookOpen, ListTree, MapPin, UserRound } from 'lucide-react'
import { useParams, useSearchParams } from 'react-router'

import { useEntities, useSeries } from '@/api/queries'
import { EmptyState } from '@/components/ui/empty'
import { Select } from '@/components/ui/inputs'
import { useCreateEntity } from '@/features/entities/api'
import { EntityHeader } from '@/features/entities/EntityHeader'
import { MasterDetail } from '@/features/entities/MasterDetail'
import { SeriesRedirect } from '@/features/entities/SeriesRedirect'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'

import { CharacterEditor, LoreEditor } from './editors'
import { LORE_TYPES } from './types'
import { Outline } from './Outline'

export const LoreIndex = () => (
  <SeriesRedirect base="/lore" icon={BookOpen} what="Characters and lore" />
)

type Tab = 'characters' | 'entries' | 'outline'

export function LorePage() {
  const { seriesId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const tab: Tab =
    (['entries', 'outline'] as const).find((t) => t === params.get('tab')) ?? 'characters'
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

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col gap-4 px-6 py-6">
      <EntityHeader title="Lore" base="/lore" seriesId={seriesId}>
        <div
          role="radiogroup"
          aria-label="Lore view"
          className="ml-auto flex rounded-md border border-border bg-bg p-0.5"
        >
          {(
            [
              ['characters', 'Characters', UserRound],
              ['entries', 'Places & lore', MapPin],
              ['outline', 'Outline', ListTree],
            ] as const
          ).map(([v, label, Icon]) => (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={tab === v}
              onClick={() => set({ tab: v === 'characters' ? null : v, id: null })}
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
      {tab === 'characters' && (
        <Characters seriesId={seriesId} id={params.get('id')} select={(id) => set({ id })} />
      )}
      {tab === 'entries' && (
        <Entries seriesId={seriesId} id={params.get('id')} select={(id) => set({ id })} />
      )}
      {tab === 'outline' && (
        <OutlineTab
          seriesId={seriesId}
          bookId={params.get('book')}
          setBook={(book) => set({ book })}
        />
      )}
    </div>
  )
}

function Characters({
  seriesId,
  id,
  select,
}: {
  seriesId: string
  id: string | null
  select: (id: string | null) => void
}) {
  const list = useEntities('characters', seriesId)
  const create = useCreateEntity('characters', seriesId)
  const current = list.data?.find((c) => c.id === id)
  return (
    <MasterDetail
      label="Characters"
      createLabel="New character"
      loading={list.isPending}
      rows={(list.data ?? []).map((c) => ({
        id: c.id,
        title: c.name,
        subtitle: c.role || undefined,
      }))}
      selectedId={current ? current.id : null}
      onSelect={select}
      onCreate={(name) => create.mutate({ name }, { onSuccess: (c) => select(c.id) })}
      detail={
        current && (
          <CharacterEditor
            key={current.id}
            seriesId={seriesId}
            character={current}
            onDeleted={() => select(null)}
          />
        )
      }
      empty={
        <EmptyState icon={UserRound} title="Pick a character">
          Characters carry voice, motives and secrets for the prose writer. Mention them anywhere
          with [[key]].
        </EmptyState>
      }
    />
  )
}

function Entries({
  seriesId,
  id,
  select,
}: {
  seriesId: string
  id: string | null
  select: (id: string | null) => void
}) {
  const list = useEntities('lore', seriesId)
  const create = useCreateEntity('lore', seriesId)
  const current = list.data?.find((l) => l.id === id)
  const order = LORE_TYPES.map((t) => t.value as string)
  const rank = (t: string) => (order.includes(t) ? order.indexOf(t) : order.length)
  const sorted = [...(list.data ?? [])].sort(
    (a, b) => rank(a.type) - rank(b.type) || a.name.localeCompare(b.name),
  )
  return (
    <MasterDetail
      label="Lore entries"
      createLabel="New entry"
      loading={list.isPending}
      rows={sorted.map((l) => ({
        id: l.id,
        title: l.name,
        group: LORE_TYPES.find((t) => t.value === l.type)?.label ?? l.type,
      }))}
      selectedId={current ? current.id : null}
      onSelect={select}
      onCreate={(name) => create.mutate({ name }, { onSuccess: (l) => select(l.id) })}
      detail={
        current && (
          <LoreEditor
            key={current.id}
            seriesId={seriesId}
            entry={current}
            onDeleted={() => select(null)}
          />
        )
      }
      empty={
        <EmptyState icon={MapPin} title="Pick an entry">
          Places, factions, history and glossary terms. Nodes can be set in a location.
        </EmptyState>
      }
    />
  )
}

function OutlineTab({
  seriesId,
  bookId,
  setBook,
}: {
  seriesId: string
  bookId: string | null
  setBook: (id: string) => void
}) {
  const series = useSeries(seriesId)
  const lastBookId = useUiStore((s) => s.lastBookId)
  const books = series.data?.books ?? []
  const current =
    books.find((b) => b.id === bookId) ?? books.find((b) => b.id === lastBookId) ?? books[0]
  if (series.isPending) return <p className="text-sm text-muted">Loading…</p>
  if (!current)
    return (
      <EmptyState icon={ListTree} title="No books yet">
        Outlines belong to a book's acts.
      </EmptyState>
    )
  return (
    <div className="min-h-0 space-y-4 overflow-auto">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted">Book</span>
        <Select
          aria-label="Book"
          value={current.id}
          options={books.map((b) => ({ value: b.id, label: b.title }))}
          onValueChange={(id) => id && setBook(id)}
          className="w-auto"
        />
      </div>
      <Outline key={current.id} bookId={current.id} seriesId={seriesId} />
    </div>
  )
}
