import type { NodeProps } from '@xyflow/react'
import { Plus } from 'lucide-react'
import { memo } from 'react'

import type { ActFrameNode } from './flow'

export const ActFrame = memo(function ActFrame({ data, width, height }: NodeProps<ActFrameNode>) {
  const { act, color, count, onAdd } = data
  return (
    <div
      className="pointer-events-none rounded-2xl border-2 border-dashed"
      style={{ width, height, borderColor: `${color}66`, background: `${color}0d` }}
    >
      <div className="pointer-events-auto flex items-center gap-2 px-3 py-2">
        <span className="size-2.5 rounded-full" style={{ background: color }} aria-hidden />
        <span className="text-sm font-semibold" style={{ color }}>
          {act.title}
        </span>
        <span className="text-xs text-muted">
          {count} node{count === 1 ? '' : 's'}
        </span>
        {onAdd && (
          <button
            type="button"
            onClick={() => onAdd(act.id)}
            className="nodrag ml-1 rounded p-0.5 text-muted hover:bg-surface-2 hover:text-text"
            aria-label={`Add node to ${act.title}`}
            title={`Add node to ${act.title}`}
          >
            <Plus className="size-3.5" />
          </button>
        )}
      </div>
    </div>
  )
})
