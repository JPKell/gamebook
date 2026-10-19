import { ArrowDown, ArrowUp, Plus, ScrollText, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty'
import { Field } from '@/components/ui/field'
import { Checkbox, NumberInput, Select, TextArea, TextInput } from '@/components/ui/inputs'
import { Panel } from '@/features/entities/EntityHeader'
import { useSeriesVocab } from '@/features/entities/useSeriesVocab'
import { cn } from '@/lib/utils'

import {
  type Appendix,
  type AppendixOptions,
  useAppendices,
  useAppendixRender,
  useCreateAppendix,
  useDeleteAppendix,
  useMaps,
  useReorderAppendices,
  useUpdateAppendix,
} from './api'
import { useLatest } from './useLatest'

const KINDS: { value: Appendix['kind'] & string; label: string; hint: string }[] = [
  {
    value: 'bestiary',
    label: 'Bestiary',
    hint: 'Every enemy in the book, with stat blocks for the tier.',
  },
  {
    value: 'sheet',
    label: 'Adventure sheet',
    hint: "Boxes for the tier's stats, inventory and codewords.",
  },
  { value: 'items', label: 'Item catalogue', hint: 'Items with their modifiers and effects.' },
  { value: 'rules', label: 'Rules reference', hint: "The tier's tests and combat, condensed." },
  { value: 'personae', label: 'Dramatis personae', hint: 'The characters.' },
  { value: 'glossary', label: 'Glossary', hint: 'Lore entries of type "glossary".' },
  { value: 'maps', label: 'Maps', hint: 'Each map as a page with a marker legend.' },
  { value: 'custom', label: 'Custom page', hint: "Markdown: an author's note, credits…" },
]

/** Back matter for one book: choose, order and configure appendices, with a live preview. */
export function AppendicesView({
  bookId,
  seriesId,
  id,
  select,
}: {
  bookId: string
  seriesId: string
  id: string | null
  select: (id: string | null) => void
}) {
  const list = useAppendices(bookId)
  const create = useCreateAppendix(bookId)
  const reorder = useReorderAppendices(bookId)
  const [kind, setKind] = useState<string>('bestiary')
  const rows = list.data ?? []
  const current = rows.find((a) => a.id === id) ?? rows[0]
  const move = (i: number, d: number) => {
    const ids = rows.map((a) => a.id)
    ;[ids[i], ids[i + d]] = [ids[i + d]!, ids[i]!]
    reorder.mutate(ids)
  }
  return (
    <div className="grid h-full gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
      <div className="space-y-3">
        <div className="flex gap-2">
          <Select
            aria-label="Appendix kind"
            value={kind}
            options={KINDS}
            onValueChange={(k) => k && setKind(k)}
          />
          <Button
            size="sm"
            onClick={() =>
              create.mutate({ kind: kind as never }, { onSuccess: (a) => select(a.id) })
            }
          >
            <Plus className="size-4" /> Add
          </Button>
        </div>
        <ol aria-label="Appendices" className="space-y-1">
          {rows.map((a, i) => (
            <li key={a.id} className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => select(a.id)}
                aria-current={current?.id === a.id ? 'true' : undefined}
                className={cn(
                  'min-w-0 flex-1 truncate rounded-md px-2 py-1.5 text-left text-sm',
                  current?.id === a.id ? 'bg-accent/10 text-accent' : 'hover:bg-surface-2',
                  !a.enabled && 'text-muted line-through',
                )}
              >
                {a.title}
                <span className="block text-xs text-muted no-underline">
                  {KINDS.find((k) => k.value === a.kind)?.label}
                </span>
              </button>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Move ${a.title} up`}
                disabled={i === 0}
                onClick={() => move(i, -1)}
              >
                <ArrowUp className="size-4" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Move ${a.title} down`}
                disabled={i === rows.length - 1}
                onClick={() => move(i, 1)}
              >
                <ArrowDown className="size-4" />
              </Button>
            </li>
          ))}
        </ol>
      </div>
      {current ? (
        <AppendixEditor
          key={current.id}
          appendix={current}
          bookId={bookId}
          seriesId={seriesId}
          onDeleted={() => select(null)}
        />
      ) : (
        <EmptyState icon={ScrollText} title="No appendices yet">
          Add a bestiary, an adventure sheet, an item catalogue and more. They're generated from the
          book, so they stay up to date, and readers see them as a codex in the player.
        </EmptyState>
      )}
    </div>
  )
}

function AppendixEditor({
  appendix: a,
  bookId,
  seriesId,
  onDeleted,
}: {
  appendix: Appendix
  bookId: string
  seriesId: string
  onDeleted: () => void
}) {
  const update = useUpdateAppendix(bookId)
  const del = useDeleteAppendix(bookId)
  const render = useAppendixRender(a.id)
  const vocab = useSeriesVocab(seriesId)
  const maps = useMaps(a.kind === 'maps' ? seriesId : undefined)
  const o = a.options
  const mergeOptions = useLatest(o, update.isPending)
  const opt = (patch: Partial<AppendixOptions>) =>
    update.mutate({ id: a.id, options: mergeOptions(patch) })
  const spoilerKinds = ['bestiary', 'items', 'personae', 'maps']
  return (
    <div className="grid min-h-0 gap-4 overflow-auto xl:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
      <Panel
        title="Options"
        aside={
          <Button
            size="sm"
            variant="ghost"
            className="text-danger"
            onClick={() => del.mutate(a.id, { onSuccess: onDeleted })}
          >
            <Trash2 className="size-4" /> Remove
          </Button>
        }
      >
        <p className="text-xs text-muted">{KINDS.find((k) => k.value === a.kind)?.hint}</p>
        <Field label="Title">
          {(id) => (
            <TextInput
              id={id}
              value={a.title}
              onCommit={(title) => title && update.mutate({ id: a.id, title })}
            />
          )}
        </Field>
        <Checkbox
          label="Include in the book"
          checked={a.enabled}
          onCheckedChange={(enabled) => update.mutate({ id: a.id, enabled })}
        />
        {['bestiary', 'sheet', 'items', 'rules'].includes(a.kind) && (
          <Field label="Tier">
            {(id) => (
              <Select
                id={id}
                value={o.tier}
                placeholder="Highest tier"
                options={vocab.tiers.map((t) => ({ value: t.key, label: t.label }))}
                onValueChange={(tier) => opt({ tier })}
              />
            )}
          </Field>
        )}
        {spoilerKinds.includes(a.kind) && (
          <Field
            label="Spoilers"
            hint="Main path: only what a reader meets on the way to a victory."
          >
            {(id) => (
              <Select
                id={id}
                value={o.spoilers}
                options={[
                  { value: 'all', label: 'Show everything' },
                  { value: 'met_on_canonical_path', label: 'Main path only' },
                ]}
                onValueChange={(spoilers) => spoilers && opt({ spoilers })}
              />
            )}
          </Field>
        )}
        {(a.kind === 'bestiary' || a.kind === 'items' || a.kind === 'personae') && (
          <Checkbox
            label="Blank entries for the reader to fill in"
            checked={o.blank_entries}
            onCheckedChange={(blank_entries) => opt({ blank_entries })}
          />
        )}
        {a.kind === 'items' && (
          <Checkbox
            label="Hide key items"
            checked={o.hide_key_items}
            onCheckedChange={(hide_key_items) => opt({ hide_key_items })}
          />
        )}
        {(a.kind === 'bestiary' || a.kind === 'items' || a.kind === 'personae') && (
          <Checkbox
            label="Show portraits"
            checked={o.show_images}
            onCheckedChange={(show_images) => opt({ show_images })}
          />
        )}
        {a.kind === 'items' && (
          <Field label="Order">
            {(id) => (
              <Select
                id={id}
                value={o.order}
                options={[
                  { value: 'alpha', label: 'A to Z' },
                  { value: 'first_appearance', label: 'First appearance' },
                ]}
                onValueChange={(order) => order && opt({ order })}
              />
            )}
          </Field>
        )}
        {a.kind === 'bestiary' && (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Order">
              {(id) => (
                <Select
                  id={id}
                  value={o.order}
                  options={[
                    { value: 'alpha', label: 'A to Z' },
                    { value: 'first_appearance', label: 'First appearance' },
                  ]}
                  onValueChange={(order) => order && opt({ order })}
                />
              )}
            </Field>
            <Field label="Stats">
              {(id) => (
                <Select
                  id={id}
                  value={o.stat_mode}
                  options={[
                    { value: 'levels', label: 'Block per level' },
                    { value: 'table', label: 'Level table' },
                  ]}
                  onValueChange={(stat_mode) => stat_mode && opt({ stat_mode })}
                />
              )}
            </Field>
          </div>
        )}
        {a.kind === 'sheet' && (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Inventory lines">
              {(id) => (
                <NumberInput
                  id={id}
                  min={0}
                  max={60}
                  value={o.inventory_lines}
                  onCommit={(v) => v !== null && opt({ inventory_lines: v })}
                />
              )}
            </Field>
            <Field label="Codewords">
              {(id) => (
                <Select
                  id={id}
                  value={o.codewords}
                  options={[
                    { value: 'list', label: 'Tick list' },
                    { value: 'blank', label: 'Blank lines' },
                  ]}
                  onValueChange={(codewords) => codewords && opt({ codewords })}
                />
              )}
            </Field>
          </div>
        )}
        {a.kind === 'maps' && (
          <fieldset className="space-y-1">
            <legend className="text-xs font-medium text-muted">Maps (none ticked: all)</legend>
            {(maps.data ?? []).map((m) => (
              <div key={m.id}>
                <Checkbox
                  label={m.title}
                  checked={o.map_ids.includes(m.id)}
                  onCheckedChange={(on) =>
                    opt({
                      map_ids: on ? [...o.map_ids, m.id] : o.map_ids.filter((x) => x !== m.id),
                    })
                  }
                />
              </div>
            ))}
          </fieldset>
        )}
        {a.kind === 'custom' && (
          <Field
            label="Text"
            hint="Markdown: # headings, **bold**, *italic*, - lists, [[mentions]]."
          >
            {(id) => (
              <TextArea
                id={id}
                value={o.body}
                onCommit={(body) => opt({ body })}
                className="min-h-40 font-mono text-xs"
              />
            )}
          </Field>
        )}
        {update.error && <p className="text-xs text-danger">{update.error.message}</p>}
      </Panel>
      <section
        aria-label="Preview"
        className="min-h-[60vh] overflow-hidden rounded-xl border border-border bg-white"
      >
        {render.data ? (
          <iframe
            title={`Preview of ${a.title}`}
            srcDoc={render.data.document}
            sandbox=""
            className="h-full min-h-[60vh] w-full"
          />
        ) : (
          <p className="p-4 text-sm text-muted">
            {render.error ? render.error.message : 'Rendering…'}
          </p>
        )}
      </section>
    </div>
  )
}
