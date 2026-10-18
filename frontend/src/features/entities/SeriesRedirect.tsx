import type { LucideIcon } from 'lucide-react'
import { Link, Navigate } from 'react-router'

import { useBook, useSeriesList } from '@/api/queries'
import { buttonVariants } from '@/components/ui/button-variants'
import { EmptyState } from '@/components/ui/empty'
import { useUiStore } from '@/stores/ui'

/** /<section> → /<section>/<series of the last book, or the first series>. */
export function SeriesRedirect({
  base,
  icon,
  what,
}: {
  base: string
  icon: LucideIcon
  what: string
}) {
  const lastBookId = useUiStore((s) => s.lastBookId)
  const book = useBook(lastBookId ?? undefined)
  const series = useSeriesList()
  if (lastBookId && book.isPending) return <p className="p-6 text-muted">Loading…</p>
  const seriesId = book.data?.series_id ?? series.data?.[0]?.id
  if (seriesId) return <Navigate to={`${base}/${seriesId}`} replace />
  if (series.isPending) return <p className="p-6 text-muted">Loading…</p>
  return (
    <EmptyState
      icon={icon}
      title="No series yet"
      action={
        <Link to="/library" className={buttonVariants()}>
          Go to the Library
        </Link>
      }
    >
      {what} belong to a series. Create one in the Library first.
    </EmptyState>
  )
}
