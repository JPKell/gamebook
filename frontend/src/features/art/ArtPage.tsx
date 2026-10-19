import { BookCopy, ClipboardList, Image, Images, Map as MapIcon, ScrollText } from 'lucide-react'
import { useParams, useSearchParams } from 'react-router'

import { useSeries } from '@/api/queries'
import { Select } from '@/components/ui/inputs'
import { EntityHeader } from '@/features/entities/EntityHeader'
import { SeriesRedirect } from '@/features/entities/SeriesRedirect'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'

import { AppendicesView } from './AppendicesView'
import { BookArtView } from './BookArtView'
import { CommissioningView } from './CommissioningView'
import { LibraryView } from './LibraryView'
import { MapsView } from './MapsView'

export const ArtIndex = () => <SeriesRedirect base="/art" icon={Image} what="Images and maps" />

const VIEWS = [
  ['library', 'Library', Images],
  ['book', 'Book art', BookCopy],
  ['maps', 'Maps', MapIcon],
  ['appendices', 'Appendices', ScrollText],
  ['commissioning', 'Commissioning', ClipboardList],
] as const
type View = (typeof VIEWS)[number][0]
const BOOK_VIEWS = new Set<View>(['book', 'appendices'])

export function ArtPage() {
  const { seriesId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const view: View = VIEWS.find(([v]) => v === params.get('view'))?.[0] ?? 'library'
  const series = useSeries(seriesId)
  const lastBookId = useUiStore((s) => s.lastBookId)
  const books = series.data?.books ?? []
  const bookId =
    books.find((b) => b.id === params.get('book'))?.id ??
    books.find((b) => b.id === lastBookId)?.id ??
    books[0]?.id ??
    null
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
      <EntityHeader title="Art" base="/art" seriesId={seriesId}>
        {BOOK_VIEWS.has(view) && books.length > 0 && (
          <Select
            aria-label="Book"
            value={bookId}
            options={books.map((b) => ({ value: b.id, label: b.title }))}
            onValueChange={(b) => set({ book: b })}
            className="w-auto"
          />
        )}
        <div
          role="radiogroup"
          aria-label="Art view"
          className="ml-auto flex flex-wrap rounded-md border border-border bg-bg p-0.5"
        >
          {VIEWS.map(([v, label, Icon]) => (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={view === v}
              onClick={() => set({ view: v === 'library' ? null : v, id: null })}
              className={cn(
                'flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium',
                view === v ? 'bg-accent text-accent-fg' : 'text-muted hover:text-text',
              )}
            >
              <Icon className="size-3.5" aria-hidden /> {label}
            </button>
          ))}
        </div>
      </EntityHeader>
      <div className="min-h-0 flex-1">
        {view === 'library' && (
          <LibraryView seriesId={seriesId} id={params.get('id')} select={(id) => set({ id })} />
        )}
        {view === 'book' &&
          (bookId ? <BookArtView seriesId={seriesId} bookId={bookId} /> : <NoBooks />)}
        {view === 'maps' && (
          <MapsView
            seriesId={seriesId}
            books={books}
            id={params.get('id')}
            select={(id) => set({ id })}
          />
        )}
        {view === 'appendices' &&
          (bookId ? (
            <AppendicesView
              bookId={bookId}
              seriesId={seriesId}
              id={params.get('id')}
              select={(id) => set({ id })}
            />
          ) : (
            <NoBooks />
          ))}
        {view === 'commissioning' && <CommissioningView seriesId={seriesId} />}
      </div>
    </div>
  )
}

function NoBooks() {
  return <p className="text-sm text-muted">This series has no books yet.</p>
}
