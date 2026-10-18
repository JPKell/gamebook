import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import {
  useCreateAct,
  useDeleteAct,
  useReorderActs,
  useUpdateAct,
  useUpdateBook,
} from '@/api/mutations'
import type { BookGraph } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { NumberInput, TextArea, TextInput } from '@/components/ui/inputs'
import { Tabs } from '@/components/ui/tabs'

import { actColor, sortedActs } from './model'

export function BookDialog({
  graph,
  open,
  onOpenChange,
}: {
  graph: BookGraph
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [tab, setTab] = useState('acts')
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={graph.book.title}
      description="Changes save as you go and can be undone."
      className="w-[min(680px,calc(100vw-2rem))]"
    >
      <Tabs
        value={tab}
        onValueChange={setTab}
        className="-mx-5 -my-4"
        tabs={[
          { value: 'acts', label: 'Acts', content: <ActsEditor graph={graph} /> },
          { value: 'details', label: 'Details', content: <BookDetails graph={graph} /> },
        ]}
      />
    </Dialog>
  )
}

function BookDetails({ graph }: { graph: BookGraph }) {
  const book = graph.book
  const update = useUpdateBook(book.id, book.series_id)
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[1fr_6rem] gap-3">
        <Field label="Title">
          {(id) => (
            <TextInput id={id} value={book.title} onCommit={(title) => update.mutate({ title })} />
          )}
        </Field>
        <Field label="Book #">
          {(id) => (
            <NumberInput
              id={id}
              allowEmpty
              value={book.number ?? null}
              onCommit={(number) => update.mutate({ number })}
            />
          )}
        </Field>
      </div>
      <Field label="Synopsis">
        {(id) => (
          <TextArea
            id={id}
            value={book.synopsis}
            onCommit={(synopsis) => update.mutate({ synopsis })}
          />
        )}
      </Field>
      <p className="text-xs text-muted">
        Style overrides for this book arrive with the writing tools (Phase 7); the series style
        guide applies until then.
      </p>
    </div>
  )
}

function ActsEditor({ graph }: { graph: BookGraph }) {
  const bookId = graph.book.id
  const acts = sortedActs(graph)
  const create = useCreateAct(bookId)
  const update = useUpdateAct(bookId)
  const remove = useDeleteAct(bookId)
  const reorder = useReorderActs(bookId)
  const counts = new Map<string, number>()
  for (const n of graph.nodes) counts.set(n.act_id, (counts.get(n.act_id) ?? 0) + 1)

  const move = (index: number, delta: number) => {
    const ids = acts.map((a) => a.id)
    const [id] = ids.splice(index, 1)
    ids.splice(index + delta, 0, id!)
    reorder.mutate(ids)
  }

  return (
    <div className="space-y-3">
      <ol className="space-y-3">
        {acts.map((act, i) => (
          <li key={act.id} className="rounded-lg border border-border p-3">
            <div className="flex items-center gap-2">
              <input
                type="color"
                aria-label={`${act.title} colour`}
                value={actColor(act, i)}
                onChange={(e) => update.mutate({ id: act.id, color: e.target.value })}
                className="size-8 shrink-0 cursor-pointer rounded border border-border bg-transparent"
              />
              <TextInput
                aria-label="Act title"
                value={act.title}
                onCommit={(title) => update.mutate({ id: act.id, title })}
                className="font-medium"
              />
              <span className="shrink-0 text-xs text-muted tabular-nums">
                {counts.get(act.id) ?? 0} nodes
              </span>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Move up"
                disabled={i === 0}
                onClick={() => move(i, -1)}
              >
                <ArrowUp className="size-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Move down"
                disabled={i === acts.length - 1}
                onClick={() => move(i, 1)}
              >
                <ArrowDown className="size-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete ${act.title}`}
                disabled={acts.length === 1}
                onClick={() => {
                  const n = counts.get(act.id) ?? 0
                  if (
                    n === 0 ||
                    window.confirm(`Delete ${act.title} and its ${n} node(s)? You can undo this.`)
                  )
                    remove.mutate({ id: act.id, force: n > 0 })
                }}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
            <TextArea
              aria-label={`${act.title} summary`}
              placeholder="What happens in this act…"
              value={act.summary}
              onCommit={(summary) => update.mutate({ id: act.id, summary })}
              className="mt-2 min-h-12 text-sm"
            />
          </li>
        ))}
      </ol>
      <Button
        variant="outline"
        size="sm"
        onClick={() => create.mutate({ title: `Act ${acts.length + 1}` })}
      >
        <Plus className="size-4" /> Add act
      </Button>
    </div>
  )
}
