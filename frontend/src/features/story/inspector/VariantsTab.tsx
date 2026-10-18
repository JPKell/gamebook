import { Plus, Trash2 } from 'lucide-react'

import { useCreateVariant, useDeleteVariant, useUpdateVariant } from '@/api/mutations'
import type { BookGraph, NodeOut } from '@/api/types'
import { GbxField } from '@/components/gbx/GbxField'
import { Button } from '@/components/ui/button'
import { NumberInput, TextInput } from '@/components/ui/inputs'

export function VariantsTab({ graph, node }: { graph: BookGraph; node: NodeOut }) {
  const bookId = graph.book.id
  const create = useCreateVariant(bookId)
  const update = useUpdateVariant(bookId)
  const remove = useDeleteVariant(bookId)

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        Different text for different situations — e.g. returning visits or carrying a codeword. The
        reader sees the highest-priority variant whose condition holds; keep one without a condition
        as the default. Print editions turn variants into separate sections.
      </p>
      {node.variants.map((v) => (
        <div key={v.id} className="space-y-2 rounded-lg border border-border p-3">
          <div className="flex items-center gap-2">
            <TextInput
              aria-label="Variant name"
              value={v.label}
              onCommit={(label) => update.mutate({ id: v.id, label })}
            />
            <label className="flex items-center gap-1 text-xs text-muted" title="Higher wins">
              Priority
              <NumberInput
                aria-label="Priority"
                value={v.priority}
                onCommit={(priority) => update.mutate({ id: v.id, priority: priority ?? 0 })}
                className="w-14 px-1.5"
              />
            </label>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Delete variant"
              disabled={node.variants.length === 1}
              onClick={() => remove.mutate(v.id)}
            >
              <Trash2 className="size-4" />
            </Button>
          </div>
          <GbxField
            label="Shown when"
            context="condition"
            value={v.condition ?? null}
            placeholder="e.g. visits(this_node) > 1"
            emptyHint="Default text (always applies)."
            onCommit={(condition) => update.mutate({ id: v.id, condition })}
          />
        </div>
      ))}
      <Button
        variant="outline"
        size="sm"
        onClick={() =>
          create.mutate({
            nodeId: node.id,
            label: 'Returning',
            condition: `visits(${node.key}) > 1`,
            priority: 1,
          })
        }
      >
        <Plus className="size-4" /> Add variant
      </Button>
    </div>
  )
}
