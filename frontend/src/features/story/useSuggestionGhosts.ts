import { type Edge, MarkerType } from '@xyflow/react'
import { useMemo } from 'react'

import type { BookGraph } from '@/api/types'
import {
  type AssistItem,
  type SuggestionPayload,
  useAcceptSuggestion,
  useAssistItems,
  useRejectSuggestion,
} from '@/features/assist/api'

import type { GhostFlowNode } from './canvas/GhostCard'

/** Same rule as the backend's ``free_spot``: move down past existing cards. */
function freeSpot(x: number, y: number, taken: { x: number; y: number }[]) {
  let yy = y
  for (
    let i = 0;
    i < 200 && taken.some((t) => Math.abs(t.x - x) < 260 && Math.abs(t.y - yy) < 130);
    i++
  )
    yy += 140
  return { x, y: yy }
}

export const isOpenSuggestion = (i: AssistItem) => i.status === 'open' || i.status === 'partial'
const open = isOpenSuggestion

/** Open suggestions as dashed nodes and edges for the canvas. */
export function useSuggestionGhosts(bookId: string, graph: BookGraph) {
  const items = useAssistItems(bookId, 'suggestion')
  const accept = useAcceptSuggestion(bookId)
  const reject = useRejectSuggestion(bookId)
  const busy = accept.isPending || reject.isPending
  // mutate is stable across renders; the mutation objects are not (they would
  // rebuild the ghost nodes on every render and React Flow would never settle).
  const acceptMutate = accept.mutate
  const rejectMutate = reject.mutate
  return useMemo(() => {
    const nodes: GhostFlowNode[] = []
    const edges: Edge[] = []
    const byKey = new Map(graph.nodes.map((n) => [n.key, n]))
    const taken = graph.nodes.map((n) => ({ x: n.x, y: n.y }))
    for (const item of (items.data ?? []).filter(open)) {
      const p = item.payload as unknown as SuggestionPayload
      const ghostId = (ref: string) => `ghost:${item.id}:${ref}`
      const endpoint = (name: string) => {
        const pending = p.nodes.find((n) => n.ref === name)
        if (pending) return pending.status === 'pending' ? ghostId(name) : (pending.node_id ?? null)
        return byKey.get(name)?.id ?? null
      }
      ;[...p.nodes]
        .filter((n) => n.status === 'pending')
        .sort((a, b) => (a.ref < b.ref ? -1 : 1)) // same order as the backend places them
        .forEach((n) => {
          const from = p.choices.find((c) => c.to === n.ref && byKey.has(c.from))
          const src = from ? byKey.get(from.from) : undefined
          const position =
            n.x !== undefined && n.y !== undefined
              ? { x: n.x, y: n.y }
              : freeSpot(src ? src.x + 320 : 0, src ? src.y : 0, taken)
          taken.push(position)
          nodes.push({
            id: ghostId(n.ref),
            type: 'ghost',
            position,
            draggable: false,
            // Selectable so React Flow keeps pointer events on (its selection
            // changes are ignored by the canvas): the card's buttons must click.
            selectable: true,
            data: {
              title: n.title,
              beatNotes: n.beat_notes,
              busy,
              onAccept: () => acceptMutate({ id: item.id, nodes: [n.ref] }),
              onReject: () => rejectMutate({ id: item.id, nodes: [n.ref] }),
            },
          })
        })
      p.choices.forEach((c, i) => {
        if (c.status !== 'pending') return
        const source = endpoint(c.from)
        const target = endpoint(c.to)
        if (!source || !target) return
        edges.push({
          id: `ghost-edge:${item.id}:${i}`,
          source,
          target,
          label: c.label,
          animated: true,
          style: { strokeDasharray: '6 4', stroke: 'var(--accent)' },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 14,
            height: 14,
            color: 'var(--accent)',
          },
          selectable: false,
        })
      })
    }
    return { nodes, edges }
  }, [items.data, graph.nodes, acceptMutate, rejectMutate, busy])
}
