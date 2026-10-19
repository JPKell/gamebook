import { useQueryClient } from '@tanstack/react-query'
import { Check, ScrollText, Sparkles, X } from 'lucide-react'
import { useState } from 'react'

import { useBookGraph, useSeries } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty'
import { Select } from '@/components/ui/inputs'
import {
  type AssistItem,
  type LorePayload,
  useAcceptLore,
  useAssistItems,
  useExtractLore,
  useSetAssistStatus,
} from '@/features/assist/api'
import { isActive, useJobStream } from '@/features/playtest/api'
import { useUiStore } from '@/stores/ui'

import { LORE_TYPES } from './types'

const LABELS: Record<string, string> = {
  name: 'Name',
  role: 'Role',
  appearance: 'Appearance',
  voice: 'Voice',
  motivations: 'Motivations',
  secrets: 'Secrets',
  notes: 'Notes',
  body: 'Text',
}

/** Characters and lore the extractor found in approved prose, for review. */
export function LoreDrafts({ seriesId }: { seriesId: string }) {
  const series = useSeries(seriesId)
  const lastBookId = useUiStore((s) => s.lastBookId)
  const books = series.data?.books ?? []
  const [bookId, setBookId] = useState<string | null>(null)
  const book =
    books.find((b) => b.id === bookId) ?? books.find((b) => b.id === lastBookId) ?? books[0]
  if (series.isPending) return <p className="text-sm text-muted">Loading…</p>
  if (!book)
    return (
      <EmptyState icon={ScrollText} title="No books yet">
        Lore is read from a book's approved prose.
      </EmptyState>
    )
  return (
    <div className="min-h-0 space-y-4 overflow-auto">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted">Book</span>
        <Select
          aria-label="Book"
          value={book.id}
          options={books.map((b) => ({ value: b.id, label: b.title }))}
          onValueChange={(id) => id && setBookId(id)}
          className="w-auto"
        />
      </div>
      <Drafts key={book.id} bookId={book.id} seriesId={seriesId} />
    </div>
  )
}

function Drafts({ bookId, seriesId }: { bookId: string; seriesId: string }) {
  const qc = useQueryClient()
  const graph = useBookGraph(bookId)
  const items = useAssistItems(bookId, 'lore')
  const extract = useExtractLore(bookId)
  const [actId, setActId] = useState<string | null>(null)
  const job = useJobStream(
    extract.data?.id,
    () => void qc.invalidateQueries({ queryKey: ['book', bookId] }),
  )
  const drafts = (items.data ?? []).filter((d) => d.status === 'open')
  const running = extract.isPending || isActive(job?.status)
  return (
    <div className="space-y-4">
      <section
        aria-label="Extract lore"
        className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface p-3"
      >
        <p className="min-w-64 flex-1 text-sm text-muted">
          Reads approved prose and proposes new characters and places, or new facts about ones you
          have. Nothing is saved until you accept it.
        </p>
        <Select
          aria-label="Act"
          className="w-auto"
          value={actId}
          placeholder="Whole book"
          options={(graph.data?.acts ?? []).map((a) => ({ value: a.id, label: a.title }))}
          onValueChange={setActId}
        />
        <Button disabled={running} onClick={() => extract.mutate(actId)}>
          <Sparkles className="size-4" /> {running ? 'Reading…' : 'Read the prose'}
        </Button>
        {job && !running && (
          <p
            role="status"
            className={
              job.status === 'done' ? 'w-full text-sm text-success' : 'w-full text-sm text-danger'
            }
          >
            {job.status === 'done'
              ? `${(job.result as { drafts: number }).drafts} new draft(s).`
              : job.error}
          </p>
        )}
      </section>
      {drafts.length === 0 ? (
        <p className="text-sm text-muted">No drafts waiting.</p>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {drafts.map((d) => (
            <DraftCard key={d.id} item={d} bookId={bookId} seriesId={seriesId} />
          ))}
        </ul>
      )}
    </div>
  )
}

function DraftCard({
  item,
  bookId,
  seriesId,
}: {
  item: AssistItem
  bookId: string
  seriesId: string
}) {
  const p = item.payload as unknown as LorePayload
  const accept = useAcceptLore(bookId, seriesId)
  const status = useSetAssistStatus(bookId)
  const [fields, setFields] = useState<Record<string, string>>(p.fields)
  const update = !!p.existing_id
  const heading = update
    ? `Update ${p.target === 'character' ? 'character' : 'entry'}: ${p.fields.name}`
    : `New ${p.target === 'character' ? 'character' : (LORE_TYPES.find((t) => t.value === p.fields.type)?.label.toLowerCase() ?? 'entry')}: ${p.fields.name}`
  return (
    <li
      aria-label={heading}
      className="space-y-2 rounded-xl border border-border bg-surface p-3 text-sm"
    >
      <h3 className="font-semibold">{heading}</h3>
      {p.evidence && <q className="block text-xs text-muted italic">{p.evidence}</q>}
      {update && (
        <p className="text-xs text-muted">Accepting adds the new text to the existing entry.</p>
      )}
      {Object.entries(fields)
        // New entries show every field; updates only the fields with new text.
        .filter(([k, v]) => k !== 'type' && (k === 'name' || k === 'body' || !update || v))
        .map(([k, v]) => (
          <label key={k} className="block space-y-0.5">
            <span className="text-xs font-medium text-muted">{LABELS[k] ?? k}</span>
            {k === 'name' ? (
              <input
                value={v}
                disabled={update}
                onChange={(e) => setFields({ ...fields, [k]: e.target.value })}
                className="w-full rounded-md border border-border bg-bg px-2 py-1"
              />
            ) : (
              <textarea
                rows={2}
                value={v}
                onChange={(e) => setFields({ ...fields, [k]: e.target.value })}
                className="w-full rounded-md border border-border bg-bg px-2 py-1"
              />
            )}
          </label>
        ))}
      {p.target === 'lore' && !update && (
        <Select
          aria-label="Type"
          value={fields.type ?? 'other'}
          options={LORE_TYPES}
          onValueChange={(t) => t && setFields({ ...fields, type: t })}
        />
      )}
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={accept.isPending}
          onClick={() => accept.mutate({ id: item.id, fields })}
        >
          <Check className="size-4" /> {update ? 'Add to entry' : 'Create'}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => status.mutate({ id: item.id, status: 'rejected' })}
        >
          <X className="size-4" /> Reject
        </Button>
      </div>
    </li>
  )
}
