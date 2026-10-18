import { BookOpen, BookPlus, Library, MoreHorizontal, Plus, Settings2, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import { useCreateBook, useCreateSeries, useDeleteBook, useDeleteSeries } from '@/api/mutations'
import { useSeries, useSeriesList } from '@/api/queries'
import type { SeriesSummary } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty'
import { Field, controlClass } from '@/components/ui/field'
import { Menu, MenuItem } from '@/components/ui/menu'

import { SeriesSettingsDialog } from './SeriesSettingsDialog'

export function LibraryPage() {
  const series = useSeriesList()
  const [creating, setCreating] = useState(false)

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Library</h1>
          <p className="text-sm text-muted">Your series and the books in them.</p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="size-4" /> New series
        </Button>
      </header>

      {series.isPending ? (
        <p className="text-muted">Loading…</p>
      ) : series.data?.length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {series.data.map((s) => (
            <SeriesCard key={s.id} series={s} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Library}
          title="No series yet"
          action={
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" /> Create your first series
            </Button>
          }
        >
          A series is a shared world: its books share items, enemies, lore and rules.
        </EmptyState>
      )}

      <NameDialog
        open={creating}
        onOpenChange={setCreating}
        title="New series"
        description="A shared world for one or more books. You can change everything later."
        label="Series title"
        extraLabel="Description"
        submitLabel="Create series"
        useSubmit={useCreateSeries}
        toBody={(title, description) => ({ title, description })}
      />
    </div>
  )
}

function SeriesCard({ series }: { series: SeriesSummary }) {
  const detail = useSeries(series.id)
  const navigate = useNavigate()
  const [addingBook, setAddingBook] = useState(false)
  const [settings, setSettings] = useState(false)
  const deleteSeries = useDeleteSeries()
  const deleteBook = useDeleteBook()
  const books = detail.data?.books ?? []

  return (
    <section
      className="flex flex-col rounded-xl border border-border bg-surface"
      aria-label={series.title}
    >
      <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <h2 className="truncate font-semibold">{series.title}</h2>
          {series.description && (
            <p className="line-clamp-2 text-sm text-muted">{series.description}</p>
          )}
        </div>
        <Menu
          trigger={
            <Button variant="ghost" size="icon" aria-label={`${series.title} options`}>
              <MoreHorizontal className="size-4" />
            </Button>
          }
        >
          <MenuItem icon={<Settings2 />} onSelect={() => setSettings(true)}>
            Series settings & style
          </MenuItem>
          <MenuItem
            icon={<Trash2 />}
            danger
            onSelect={() => {
              if (
                window.confirm(
                  `Delete "${series.title}" and all its books? This can't be undone (but checkpoints can restore it).`,
                )
              )
                deleteSeries.mutate(series.id)
            }}
          >
            Delete series
          </MenuItem>
        </Menu>
      </div>
      <ul className="flex-1 divide-y divide-border">
        {books.map((b) => (
          <li key={b.id} className="group flex items-center gap-2 px-4 py-2">
            <span className="w-6 text-right text-xs text-muted tabular-nums">{b.number ?? ''}</span>
            <button
              type="button"
              onClick={() => navigate(`/story/${b.id}`)}
              className="flex min-w-0 flex-1 items-center gap-2 text-left hover:text-accent"
            >
              <BookOpen className="size-4 shrink-0 text-muted" aria-hidden />
              <span className="truncate">{b.title}</span>
            </button>
            <Button
              variant="ghost"
              size="sm"
              className="opacity-0 group-hover:opacity-100 focus:opacity-100"
              aria-label={`Delete ${b.title}`}
              onClick={() => {
                if (window.confirm(`Delete "${b.title}"?`))
                  deleteBook.mutate({ id: b.id, seriesId: series.id })
              }}
            >
              <Trash2 className="size-3.5" />
            </Button>
          </li>
        ))}
        {detail.isSuccess && books.length === 0 && (
          <li className="px-4 py-3 text-sm text-muted">No books yet.</li>
        )}
      </ul>
      <div className="border-t border-border px-3 py-2">
        <Button variant="ghost" size="sm" onClick={() => setAddingBook(true)}>
          <BookPlus className="size-4" /> New book
        </Button>
      </div>

      <NameDialog
        open={addingBook}
        onOpenChange={setAddingBook}
        title={`New book in ${series.title}`}
        description="New books start with one act and a start node."
        label="Book title"
        extraLabel="Synopsis"
        submitLabel="Create book"
        useSubmit={useCreateBook}
        toBody={(title, synopsis) => ({ seriesId: series.id, title, synopsis })}
        onCreated={(b) => navigate(`/story/${(b as { id: string }).id}`)}
      />
      {settings && detail.data && (
        <SeriesSettingsDialog series={detail.data} open={settings} onOpenChange={setSettings} />
      )}
    </section>
  )
}

/** Small "title + optional text" create dialog. */
function NameDialog<TBody, TData>({
  open,
  onOpenChange,
  title,
  description,
  label,
  extraLabel,
  submitLabel,
  useSubmit,
  toBody,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  label: string
  extraLabel: string
  submitLabel: string
  useSubmit: () => { mutateAsync: (body: TBody) => Promise<TData>; isPending: boolean }
  toBody: (name: string, extra: string) => TBody
  onCreated?: (data: TData) => void
}) {
  const [name, setName] = useState('')
  const [extra, setExtra] = useState('')
  const submit = useSubmit()
  const save = async () => {
    if (!name.trim()) return
    const data = await submit.mutateAsync(toBody(name.trim(), extra.trim()))
    setName('')
    setExtra('')
    onOpenChange(false)
    onCreated?.(data)
  }
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={save} disabled={!name.trim() || submit.isPending}>
            {submitLabel}
          </Button>
        </>
      }
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          void save()
        }}
      >
        <Field label={label}>
          {(id) => (
            <input
              id={id}
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={controlClass}
            />
          )}
        </Field>
        <Field label={extraLabel}>
          {(id) => (
            <textarea
              id={id}
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
              rows={3}
              className={controlClass}
            />
          )}
        </Field>
        <button type="submit" hidden />
      </form>
    </Dialog>
  )
}
