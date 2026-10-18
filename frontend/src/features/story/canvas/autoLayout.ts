/** ELK layered layout per act; acts are laid out left → right.
 * ELK is large, so it's loaded on first use rather than with the app. */
import type { ELK as ElkInstance } from 'elkjs/lib/elk-api'

import type { BookGraph } from '@/api/types'

import { sortedActs } from '../model'
import { NODE_HEIGHT_ESTIMATE, NODE_WIDTH } from './flow'

const ACT_GAP = 200
let elkPromise: Promise<ElkInstance> | null = null

function loadElk(): Promise<ElkInstance> {
  elkPromise ??= import('elkjs/lib/elk.bundled.js').then((m) => new m.default())
  return elkPromise
}

export async function autoLayout(
  graph: BookGraph,
  sizes: Map<string, { width: number; height: number }>,
): Promise<{ id: string; x: number; y: number }[]> {
  const elk = await loadElk()
  const positions: { id: string; x: number; y: number }[] = []
  let offsetX = 0
  for (const act of sortedActs(graph)) {
    const members = graph.nodes.filter((n) => n.act_id === act.id)
    if (!members.length) continue
    const ids = new Set(members.map((n) => n.id))
    const edges = members.flatMap((n) =>
      n.choices.flatMap((c) =>
        c.outcomes
          .filter((o) => o.target_node_id && ids.has(o.target_node_id) && o.target_node_id !== n.id)
          .map((o) => ({ id: `${c.id}:${o.key}`, sources: [n.id], targets: [o.target_node_id!] })),
      ),
    )
    // Start node and act entries first so the layout reads left to right.
    const ordered = [...members].sort(
      (a, b) =>
        Number(b.id === graph.book.start_node_id) - Number(a.id === graph.book.start_node_id) ||
        Number(b.is_act_entry) - Number(a.is_act_entry),
    )
    const result = await elk.layout({
      id: act.id,
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'RIGHT',
        'elk.spacing.nodeNode': '40',
        'elk.layered.spacing.nodeNodeBetweenLayers': '90',
        'elk.layered.crossingMinimization.semiInteractive': 'true',
      },
      children: ordered.map((n) => ({
        id: n.id,
        width: sizes.get(n.id)?.width ?? NODE_WIDTH,
        height: sizes.get(n.id)?.height ?? NODE_HEIGHT_ESTIMATE,
      })),
      edges,
    })
    let maxX = 0
    for (const child of result.children ?? []) {
      const x = offsetX + (child.x ?? 0)
      positions.push({ id: child.id, x: Math.round(x), y: Math.round(child.y ?? 0) })
      maxX = Math.max(maxX, x + (child.width ?? NODE_WIDTH))
    }
    offsetX = maxX + ACT_GAP
  }
  return positions
}
