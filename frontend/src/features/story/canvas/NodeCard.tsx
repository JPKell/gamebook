import { Handle, type NodeProps, Position } from '@xyflow/react'
import {
  CircleAlert,
  CircleX,
  Flag,
  Gem,
  Layers,
  Lock,
  LogIn,
  LogOut,
  Skull,
  Store,
  Swords,
  Trophy,
  Undo2,
  Zap,
} from 'lucide-react'
import { memo, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

import { useHeat } from '../heat'

import type { StoryFlowNode } from './flow'

const ENDING: Record<string, { icon: typeof Trophy; label: string; className: string }> = {
  victory: { icon: Trophy, label: 'Victory', className: 'text-success border-success/60' },
  death: { icon: Skull, label: 'Death', className: 'text-danger border-danger/60' },
  dead_end: { icon: Undo2, label: 'Dead end', className: 'text-muted border-border' },
}

function Badge({ icon, label, count }: { icon: ReactNode; label: string; count?: number }) {
  return (
    <span title={label} className="inline-flex items-center gap-0.5 text-muted [&_svg]:size-3.5">
      {icon}
      {count !== undefined && count > 1 && (
        <span className="text-[10px] tabular-nums">{count}</span>
      )}
      <span className="sr-only">{label}</span>
    </span>
  )
}

/** Playtest overlay: share of runs that visited this node, and deaths here. */
function HeatStrip({ id }: { id: string }) {
  const heat = useHeat()
  if (!heat) return null
  const visits = heat.visits[id] ?? 0
  const deaths = heat.deaths[id] ?? 0
  const share = heat.runs ? visits / heat.runs : 0
  return (
    <div
      className="flex items-center gap-2 border-t border-border px-2.5 py-1 text-[11px] tabular-nums"
      title={`${visits} of ${heat.runs} runs visited · ${deaths} died here`}
    >
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <span
          className="block h-full rounded-full"
          style={{ width: `${share * 100}%`, background: 'var(--series-1)' }}
        />
      </span>
      {visits === 0 ? (
        <span className="font-medium text-warning">never visited</span>
      ) : (
        <span className="text-muted">{Math.round(share * 100)}%</span>
      )}
      {deaths > 0 && (
        <span className="flex items-center gap-0.5 text-danger">
          <Skull className="size-3" aria-hidden />
          {deaths}
          <span className="sr-only">deaths</span>
        </span>
      )}
    </div>
  )
}

function NodeCardImpl({ data, selected }: NodeProps<StoryFlowNode>) {
  const { node, actColor, isStart, problems, dimmed } = data
  const ending = node.ending_kind ? ENDING[node.ending_kind] : undefined
  const gated = node.choices.filter((c) => c.condition).length
  const roles: string[] = []
  if (isStart) roles.push('Start')
  if (node.is_act_entry) roles.push('Entry')
  if (node.is_act_exit) roles.push('Exit')

  return (
    <div
      className={cn(
        'group relative w-60 rounded-lg border bg-surface text-left shadow-sm transition-[opacity,box-shadow]',
        selected ? 'border-accent ring-2 ring-accent/40' : 'border-border',
        ending && !selected && ending.className.split(' ')[1],
        dimmed && 'opacity-30',
      )}
      style={{ borderLeft: `4px solid ${actColor}` }}
      aria-label={`${node.title}${roles.length ? ` (${roles.join(', ')})` : ''}`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!size-2.5 !border-2 !border-surface !bg-muted"
      />
      <div className="flex items-center gap-1.5 px-2.5 pt-2 text-[10px] font-medium tracking-wide text-muted uppercase">
        {isStart && <Flag className="size-3 text-accent" aria-hidden />}
        {node.is_act_entry && <LogIn className="size-3" aria-hidden />}
        {node.is_act_exit && <LogOut className="size-3" aria-hidden />}
        <span className="truncate font-mono normal-case">{node.key}</span>
        {roles.length > 0 && <span className="truncate">· {roles.join(' · ')}</span>}
        <span className="ml-auto flex items-center gap-1">
          {problems?.errors ? (
            <span
              title={problems.messages.join('\n')}
              className="flex items-center gap-0.5 text-danger"
            >
              <CircleX className="size-3.5" aria-hidden />
              {problems.errors}
              <span className="sr-only">errors</span>
            </span>
          ) : null}
          {problems?.warnings ? (
            <span
              title={problems.messages.join('\n')}
              className="flex items-center gap-0.5 text-warning"
            >
              <CircleAlert className="size-3.5" aria-hidden />
              {problems.warnings}
              <span className="sr-only">warnings</span>
            </span>
          ) : null}
        </span>
      </div>
      <div className="flex items-start gap-2 px-2.5 pt-0.5 pb-1">
        <span className="min-w-0 flex-1 text-sm leading-snug font-semibold">{node.title}</span>
        {node.art_thumb && (
          <img
            src={node.art_thumb}
            alt=""
            loading="lazy"
            className="size-9 shrink-0 rounded border border-border object-cover"
          />
        )}
      </div>
      {node.beat_notes && (
        <p className="line-clamp-2 px-2.5 text-xs leading-snug text-muted">{node.beat_notes}</p>
      )}
      <div className="flex min-h-6 items-center gap-2 px-2.5 py-1.5">
        {ending && (
          <span
            className={cn(
              'inline-flex items-center gap-1 text-xs font-medium',
              ending.className.split(' ')[0],
            )}
          >
            <ending.icon className="size-3.5" aria-hidden />
            {node.ending_label || ending.label}
          </span>
        )}
        {node.encounters.length > 0 && (
          <Badge icon={<Swords />} label="Encounters" count={node.encounters.length} />
        )}
        {node.items.length > 0 && (
          <Badge icon={<Gem />} label="Items found" count={node.items.length} />
        )}
        {node.is_shop && <Badge icon={<Store />} label="Shop" />}
        {gated > 0 && <Badge icon={<Lock />} label="Gated choices" count={gated} />}
        {node.on_enter.length > 0 && (
          <Badge icon={<Zap />} label="On-entry effects" count={node.on_enter.length} />
        )}
        {node.variants.length > 1 && (
          <Badge icon={<Layers />} label="Text variants" count={node.variants.length} />
        )}
      </div>
      <HeatStrip id={node.id} />
      <Handle
        type="source"
        position={Position.Right}
        className="!size-3 !border-2 !border-surface !bg-accent opacity-60 transition-opacity group-hover:opacity-100"
      />
    </div>
  )
}

export const NodeCard = memo(NodeCardImpl)
