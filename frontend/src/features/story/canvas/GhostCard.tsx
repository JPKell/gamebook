import { Handle, type Node, type NodeProps, Position } from '@xyflow/react'
import { Check, Sparkles, X } from 'lucide-react'
import { memo } from 'react'

import { NODE_WIDTH } from './flow'

export interface GhostData extends Record<string, unknown> {
  title: string
  beatNotes: string
  onAccept: () => void
  onReject: () => void
  busy: boolean
}
export type GhostFlowNode = Node<GhostData, 'ghost'>

/** A suggested section: dashed, not draggable, with accept / reject. */
function GhostCardImpl({ data }: NodeProps<GhostFlowNode>) {
  return (
    <div
      className="rounded-lg border-2 border-dashed border-accent/60 bg-accent/6 text-left"
      style={{ width: NODE_WIDTH }}
      role="group"
      aria-label={`Suggested section: ${data.title}`}
    >
      <Handle type="target" position={Position.Left} className="!size-2 !bg-accent/60" />
      <div className="flex items-center gap-1 px-2.5 pt-2 text-[10px] font-medium tracking-wide text-accent uppercase">
        <Sparkles className="size-3" aria-hidden /> Suggested
      </div>
      <div className="px-2.5 pt-0.5 text-sm font-semibold">{data.title}</div>
      {data.beatNotes && <p className="line-clamp-3 px-2.5 text-xs text-muted">{data.beatNotes}</p>}
      <div className="nodrag flex gap-1 p-2">
        <button
          type="button"
          disabled={data.busy}
          onClick={data.onAccept}
          aria-label={`Add section ${data.title}`}
          className="flex items-center gap-1 rounded-md bg-accent px-2 py-0.5 text-xs font-medium text-accent-fg hover:bg-accent/90 disabled:opacity-50"
        >
          <Check className="size-3.5" aria-hidden /> Add section
        </button>
        <button
          type="button"
          disabled={data.busy}
          onClick={data.onReject}
          aria-label={`Dismiss section ${data.title}`}
          className="flex items-center gap-1 rounded-md px-2 py-0.5 text-xs text-muted hover:bg-surface-2 hover:text-text disabled:opacity-50"
        >
          <X className="size-3.5" aria-hidden /> Dismiss
        </button>
      </div>
      <Handle type="source" position={Position.Right} className="!size-2 !bg-accent/60" />
    </div>
  )
}

export const GhostCard = memo(GhostCardImpl)
