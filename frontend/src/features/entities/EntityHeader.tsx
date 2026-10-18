import type { ReactNode } from 'react'
import { useNavigate } from 'react-router'

import { useSeriesList } from '@/api/queries'
import { Select } from '@/components/ui/inputs'

/** Page title with a series switcher; extra controls go on the right. */
export function EntityHeader({
  title,
  base,
  seriesId,
  children,
}: {
  title: string
  base: string
  seriesId: string
  children?: ReactNode
}) {
  const navigate = useNavigate()
  const series = useSeriesList()
  return (
    <header className="flex flex-wrap items-center gap-3">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <Select
        aria-label="Series"
        value={seriesId}
        onValueChange={(id) => id && navigate(`${base}/${id}`)}
        options={(series.data ?? []).map((s) => ({ value: s.id, label: s.title }))}
        className="w-auto"
      />
      {children}
    </header>
  )
}

/** A titled card section in an entity editor. */
export function Panel({
  title,
  aside,
  children,
}: {
  title: string
  aside?: ReactNode
  children: ReactNode
}) {
  return (
    <section
      aria-label={title}
      className="space-y-3 rounded-xl border border-border bg-surface p-4"
    >
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold">{title}</h2>
        <div className="ml-auto flex items-center gap-2">{aside}</div>
      </div>
      {children}
    </section>
  )
}
