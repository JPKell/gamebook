import { BaseEdge, EdgeLabelRenderer, type EdgeProps, getBezierPath } from '@xyflow/react'
import { Dices, Lock, Swords, Target } from 'lucide-react'
import { memo } from 'react'

import { cn } from '@/lib/utils'

import type { ChoiceFlowEdge } from './flow'

const KIND_COLOR: Record<string, string> = {
  goto: 'var(--muted)',
  roll: 'var(--info)',
  test: 'var(--warning)',
  combat: 'var(--danger)',
}

const KIND_ICON = { roll: Dices, test: Target, combat: Swords } as const

function ChoiceEdgeImpl(props: EdgeProps<ChoiceFlowEdge>) {
  const {
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    data,
    selected,
    markerEnd,
  } = props
  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  })
  if (!data) return null
  const kind = data.choice.kind
  const color = selected ? 'var(--accent)' : (KIND_COLOR[kind] ?? 'var(--muted)')
  const Icon = kind !== 'goto' ? KIND_ICON[kind] : null
  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        markerEnd={markerEnd}
        style={{
          stroke: color,
          strokeWidth: selected ? 2.5 : data.crossAct ? 2.25 : 1.5,
          strokeDasharray: data.choice.condition ? '6 4' : undefined,
          opacity: data.dimmed ? 0.2 : 1,
        }}
      />
      <EdgeLabelRenderer>
        <div
          className={cn(
            'nodrag nopan pointer-events-auto absolute flex max-w-44 items-center gap-1 rounded-full border bg-surface px-2 py-0.5 text-[11px] shadow-sm',
            selected ? 'border-accent text-text' : 'border-border text-muted',
            data.dimmed && 'opacity-30',
          )}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          {data.choice.condition && <Lock className="size-3 shrink-0" aria-label="Conditional" />}
          {Icon && <Icon className="size-3 shrink-0" style={{ color }} aria-hidden />}
          <span className="truncate">{data.label}</span>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}

export const ChoiceEdge = memo(ChoiceEdgeImpl)
