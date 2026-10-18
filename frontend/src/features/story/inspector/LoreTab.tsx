import { useUpdateNode } from '@/api/mutations'
import { useEntities } from '@/api/queries'
import type { BookGraph, NodeOut } from '@/api/types'
import { Field } from '@/components/ui/field'
import { Checkbox, Select } from '@/components/ui/inputs'

import { nodeOptions } from '../model'

export function LoreTab({ graph, node }: { graph: BookGraph; node: NodeOut }) {
  const seriesId = graph.book.series_id
  const update = useUpdateNode(graph.book.id)
  const lore = useEntities('lore', seriesId, graph.book.id)
  const characters = useEntities('characters', seriesId, graph.book.id)
  const incoming = new Set(
    graph.nodes
      .filter((n) => n.choices.some((c) => c.outcomes.some((o) => o.target_node_id === node.id)))
      .map((n) => n.id),
  )
  const predecessors = nodeOptions(graph)
    .filter((o) => o.value !== node.id)
    .map((o) => ({ ...o, group: incoming.has(o.value) ? 'Leads here' : 'Other nodes' }))
    .sort((a, b) => Number(b.group === 'Leads here') - Number(a.group === 'Leads here'))
  const chars = new Set(node.character_ids)

  return (
    <div className="space-y-5">
      <Field
        label="Location"
        hint="Lore entries of type “location”. Manage lore in the Lore section."
      >
        {(id) => (
          <Select
            id={id}
            value={node.location_id ?? null}
            placeholder="No location"
            onValueChange={(location_id) => update.mutate({ id: node.id, location_id })}
            options={(lore.data ?? [])
              .filter((l) => l.type === 'location')
              .map((l) => ({ value: l.id, label: l.name }))}
          />
        )}
      </Field>
      <fieldset>
        <legend className="mb-1.5 text-xs font-medium text-muted">Characters present</legend>
        {(characters.data ?? []).length === 0 ? (
          <p className="text-xs text-muted">No characters in this series yet.</p>
        ) : (
          <div className="grid grid-cols-2 gap-1.5">
            {characters.data!.map((c) => (
              <Checkbox
                key={c.id}
                label={c.name}
                checked={chars.has(c.id)}
                onCheckedChange={(on) =>
                  update.mutate({
                    id: node.id,
                    character_ids: on ? [...chars, c.id] : [...chars].filter((x) => x !== c.id),
                  })
                }
              />
            ))}
          </div>
        )}
      </fieldset>
      <Field
        label="Story-so-far comes from"
        hint="When drafting prose, the writer continues from this node. Defaults to the shortest path from the start."
      >
        {(id) => (
          <Select
            id={id}
            value={node.canonical_predecessor_id ?? null}
            placeholder="Automatic"
            onValueChange={(canonical_predecessor_id) =>
              update.mutate({ id: node.id, canonical_predecessor_id })
            }
            options={predecessors}
          />
        )}
      </Field>
    </div>
  )
}
