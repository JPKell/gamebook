import { Link } from 'react-router'

import { useUpdateNode } from '@/api/mutations'
import { STATUS_LABELS, STATUS_TONE, useNodeProse } from '@/features/writing/api'
import { cn } from '@/lib/utils'
import type { BookGraph, NodeOut, NodeUpdate } from '@/api/types'
import { Field } from '@/components/ui/field'
import { Checkbox, NumberInput, Select, TextArea, TextInput } from '@/components/ui/inputs'

import { EffectsEditor } from './EffectsEditor'

export function BeatTab({ graph, node }: { graph: BookGraph; node: NodeOut }) {
  const update = useUpdateNode(graph.book.id)
  const patch = (body: NodeUpdate) => update.mutate({ id: node.id, ...body })

  return (
    <div className="space-y-5">
      <ProseStatus graph={graph} node={node} />
      <Field label="Beat notes" hint="What happens here. The prose writer works from these notes.">
        {(id) => (
          <TextArea
            id={id}
            value={node.beat_notes}
            onCommit={(beat_notes) => patch({ beat_notes })}
            placeholder="You reach the bridge. A ghost bars the way…"
            className="min-h-32"
          />
        )}
      </Field>
      <Field label="One-line summary">
        {(id) => (
          <TextInput id={id} value={node.summary} onCommit={(summary) => patch({ summary })} />
        )}
      </Field>

      <fieldset className="space-y-2">
        <legend className="mb-1 text-xs font-medium text-muted">Role in the act</legend>
        <div className="flex flex-wrap gap-4">
          <Checkbox
            label="Act entry"
            checked={node.is_act_entry}
            onCheckedChange={(v) => patch({ is_act_entry: v })}
          />
          <Checkbox
            label="Act exit"
            checked={node.is_act_exit}
            onCheckedChange={(v) => patch({ is_act_exit: v })}
          />
        </div>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="mb-1 text-xs font-medium text-muted">Ending</legend>
        <div className="grid grid-cols-2 gap-2">
          <Select
            aria-label="Ending kind"
            value={node.ending_kind ?? null}
            placeholder="Not an ending"
            onValueChange={(ending_kind) => patch({ ending_kind })}
            options={[
              { value: 'victory', label: 'Victory' },
              { value: 'death', label: 'Death / failure' },
              { value: 'dead_end', label: 'Dead end (go back)' },
            ]}
          />
          <Select
            aria-label="Ending grade"
            value={node.ending_grade ?? null}
            placeholder="No grade"
            disabled={!node.ending_kind}
            onValueChange={(ending_grade) => patch({ ending_grade })}
            options={[
              { value: 'good', label: 'Good' },
              { value: 'neutral', label: 'Neutral' },
              { value: 'bad', label: 'Bad' },
              { value: 'secret', label: 'Secret' },
            ]}
          />
        </div>
        {node.ending_kind && (
          <TextInput
            aria-label="Ending name"
            placeholder="Ending name, e.g. “The True Path”"
            value={node.ending_label}
            onCommit={(ending_label) => patch({ ending_label })}
          />
        )}
      </fieldset>

      <Field label="On entry" hint="Applied when the reader arrives here.">
        {() => (
          <EffectsEditor
            value={node.on_enter}
            onChange={(on_enter) => patch({ on_enter })}
            emptyText="Nothing happens automatically on arrival."
          />
        )}
      </Field>

      <Field
        label="Section number (print)"
        hint="Pin this node to a fixed number; otherwise numbers are shuffled at export."
      >
        {(id) => (
          <NumberInput
            id={id}
            allowEmpty
            min={1}
            value={node.section_pin ?? null}
            onCommit={(section_pin) => patch({ section_pin })}
            className="w-28"
          />
        )}
      </Field>
    </div>
  )
}

/** One line per text variant: its prose status, linking to the Writing review. */
function ProseStatus({ graph, node }: { graph: BookGraph; node: NodeOut }) {
  const prose = useNodeProse(graph.book.id, node.id)
  const variants = prose.data?.variants ?? []
  if (!variants.length) return null
  return (
    <div
      aria-label="Prose"
      role="group"
      className="space-y-1 rounded-lg border border-border p-2.5 text-sm"
    >
      {variants.map((v) => (
        <div key={v.variant_id} className="flex items-center gap-2">
          <span className="min-w-0 flex-1 truncate text-muted">
            Prose{variants.length > 1 ? ` · ${v.label}` : ''}
          </span>
          <span className={cn('rounded-full px-2 text-xs', STATUS_TONE[v.status])}>
            {STATUS_LABELS[v.status]}
          </span>
          <Link
            to={`/writing/${graph.book.id}?variant=${v.variant_id}`}
            className="text-xs text-accent hover:underline"
          >
            {v.status === 'none' ? 'Write' : 'Open'}
          </Link>
        </div>
      ))}
    </div>
  )
}
