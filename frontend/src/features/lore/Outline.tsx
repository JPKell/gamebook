import { ArrowDown, ArrowUp, Plus, Trash2, X } from 'lucide-react'
import { Link } from 'react-router'

import { api, unwrap } from '@/api/client'
import { useUpdateAct } from '@/api/mutations'
import { useApiMutation, useBookGraph } from '@/api/queries'
import type { components } from '@/api/schema'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Select, TextArea, TextInput } from '@/components/ui/inputs'
import { useOutline } from '@/features/story/digest'

import { MentionText } from './MentionText'

type Beat = components['schemas']['BeatOut']
type BeatUpdate = components['schemas']['BeatUpdate']

/** Beat edits refresh the book (outline, problems, digest, history) and backlinks. */
function useBeatMutations(bookId: string, seriesId: string) {
  const keys = () => [
    ['book', bookId],
    ['entities', seriesId],
  ]
  const create = useApiMutation(
    ({ actId, title }: { actId: string; title: string }) =>
      unwrap(
        api.POST('/api/acts/{act_id}/beats', {
          params: { path: { act_id: actId } },
          body: { title },
        }),
      ),
    keys,
  )
  const update = useApiMutation(
    ({ id, ...body }: BeatUpdate & { id: string }) =>
      unwrap(api.PATCH('/api/beats/{beat_id}', { params: { path: { beat_id: id } }, body })),
    keys,
  )
  const remove = useApiMutation(
    (id: string) =>
      unwrap(api.DELETE('/api/beats/{beat_id}', { params: { path: { beat_id: id } } })),
    keys,
  )
  const reorder = useApiMutation(
    ({ actId, ids }: { actId: string; ids: string[] }) =>
      unwrap(
        api.PUT('/api/acts/{act_id}/beats/order', {
          params: { path: { act_id: actId } },
          body: { ids },
        }),
      ),
    keys,
  )
  return { create, update, remove, reorder }
}

/** Act summaries and ordered story beats, each linked to the nodes that tell it. */
export function Outline({ bookId, seriesId }: { bookId: string; seriesId: string }) {
  const outline = useOutline(bookId)
  const graph = useBookGraph(bookId)
  const updateAct = useUpdateAct(bookId)
  const m = useBeatMutations(bookId, seriesId)
  if (outline.isPending || graph.isPending) return <p className="text-sm text-muted">Loading…</p>
  const nodes = graph.data?.nodes ?? []

  return (
    <div className="space-y-6">
      {(outline.data?.acts ?? []).map((act) => {
        const actNodes = nodes.filter((n) => n.act_id === act.id)
        const inBeat = new Set(act.beats.flatMap((b) => b.node_ids))
        const loose = act.beats.length ? actNodes.filter((n) => !inBeat.has(n.id)) : []
        return (
          <section
            key={act.id}
            aria-label={act.title}
            className="space-y-3 rounded-xl border border-border bg-surface p-4"
            style={{ borderLeft: `4px solid ${act.color ?? 'var(--border)'}` }}
          >
            <h2 className="text-lg font-semibold">{act.title}</h2>
            <Field
              label="Act summary"
              hint="What happens in this act, for you and the prose writer."
            >
              {(id) => (
                <TextArea
                  id={id}
                  rows={2}
                  value={act.summary}
                  onCommit={(summary) => updateAct.mutate({ id: act.id, summary })}
                />
              )}
            </Field>
            <ol className="space-y-2">
              {act.beats.map((beat, i) => (
                <BeatRow
                  key={beat.id}
                  beat={beat}
                  index={i}
                  count={act.beats.length}
                  bookId={bookId}
                  seriesId={seriesId}
                  nodes={actNodes}
                  allNodes={nodes}
                  onChange={(patch) => m.update.mutate({ id: beat.id, ...patch })}
                  onDelete={() =>
                    window.confirm(`Delete beat "${beat.title}"?`) && m.remove.mutate(beat.id)
                  }
                  busy={m.update.isPending || m.reorder.isPending}
                  onMove={(d) => {
                    const ids = act.beats.map((b) => b.id)
                    ;[ids[i], ids[i + d]] = [ids[i + d]!, ids[i]!]
                    m.reorder.mutate({ actId: act.id, ids })
                  }}
                />
              ))}
            </ol>
            <Button
              size="sm"
              variant="outline"
              onClick={() => m.create.mutate({ actId: act.id, title: 'New beat' })}
            >
              <Plus className="size-4" /> Add beat
            </Button>
            {loose.length > 0 && (
              <p className="text-xs text-muted">
                Not in any beat yet:{' '}
                {loose.map((n, i) => (
                  <span key={n.id}>
                    {i > 0 && ', '}
                    <Link
                      to={`/story/${bookId}?node=${n.id}`}
                      className="text-accent hover:underline"
                    >
                      {n.title}
                    </Link>
                  </span>
                ))}
              </p>
            )}
          </section>
        )
      })}
    </div>
  )
}

function BeatRow({
  beat,
  index,
  count,
  bookId,
  seriesId,
  nodes,
  allNodes,
  onChange,
  onDelete,
  onMove,
  busy,
}: {
  beat: Beat
  index: number
  count: number
  bookId: string
  seriesId: string
  nodes: { id: string; title: string }[]
  allNodes: { id: string; title: string }[]
  onChange: (patch: BeatUpdate) => void
  onDelete: () => void
  onMove: (delta: -1 | 1) => void
  /** A save is in flight: block edits built from the not-yet-refreshed outline. */
  busy: boolean
}) {
  const linked = beat.node_ids.map((id) => allNodes.find((n) => n.id === id)).filter(Boolean) as {
    id: string
    title: string
  }[]
  const options = nodes
    .filter((n) => !beat.node_ids.includes(n.id))
    .map((n) => ({ value: n.id, label: n.title }))
  return (
    <li
      aria-label={`Beat ${index + 1}: ${beat.title}`}
      className="space-y-2 rounded-lg border border-border p-3"
    >
      <div className="flex items-center gap-2">
        <span className="w-6 text-sm text-muted tabular-nums">{index + 1}.</span>
        <TextInput
          aria-label="Beat title"
          className="flex-1 font-medium"
          value={beat.title}
          onCommit={(title) => title.trim() && onChange({ title })}
        />
        <Button
          size="icon"
          variant="ghost"
          aria-label="Move beat up"
          disabled={busy || index === 0}
          onClick={() => onMove(-1)}
        >
          <ArrowUp className="size-4" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          aria-label="Move beat down"
          disabled={busy || index === count - 1}
          onClick={() => onMove(1)}
        >
          <ArrowDown className="size-4" />
        </Button>
        <Button size="icon" variant="ghost" aria-label="Delete beat" onClick={onDelete}>
          <Trash2 className="size-4" />
        </Button>
      </div>
      <TextArea
        aria-label="Beat description"
        rows={2}
        placeholder="What happens. Link people and places with [[key]]."
        value={beat.description}
        onCommit={(description) => onChange({ description })}
      />
      {beat.description.includes('[[') && (
        <MentionText
          text={beat.description}
          seriesId={seriesId}
          className="rounded-md bg-surface-2 px-3 py-2 text-sm"
        />
      )}
      <div className="flex flex-wrap items-center gap-1.5">
        {linked.map((n) => (
          <span
            key={n.id}
            className="inline-flex items-center gap-1 rounded-full bg-accent/12 py-0.5 pr-1 pl-2.5 text-xs text-accent"
          >
            <Link to={`/story/${bookId}?node=${n.id}`} className="hover:underline">
              {n.title}
            </Link>
            <button
              type="button"
              aria-label={`Unlink ${n.title}`}
              disabled={busy}
              onClick={() => onChange({ node_ids: beat.node_ids.filter((x) => x !== n.id) })}
              className="rounded-full p-0.5 hover:bg-accent/20"
            >
              <X className="size-3" />
            </button>
          </span>
        ))}
        {linked.length === 0 && <span className="text-xs text-muted">No nodes yet.</span>}
        <Select
          aria-label="Link a node"
          className="h-7 w-auto py-0 text-xs"
          value={null}
          placeholder="+ Link a node…"
          options={options}
          disabled={busy}
          onValueChange={(id) => id && onChange({ node_ids: [...beat.node_ids, id] })}
        />
      </div>
    </li>
  )
}
