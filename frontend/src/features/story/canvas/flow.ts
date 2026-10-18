/** Book graph → React Flow nodes/edges, and act frames from node positions. */
import type { Edge, Node } from '@xyflow/react'

import type { ActOut, BookGraph, ChoiceOut, NodeOut } from '@/api/types'

import { actColor, type ProblemSummary, sortedActs } from '../model'

export const NODE_WIDTH = 240
export const NODE_HEIGHT_ESTIMATE = 110
export const FRAME_PADDING = 32
export const FRAME_HEADER = 36

export interface StoryNodeData extends Record<string, unknown> {
  node: NodeOut
  actColor: string
  isStart: boolean
  problems: ProblemSummary | undefined
  dimmed: boolean
}

export interface ActFrameData extends Record<string, unknown> {
  act: ActOut
  color: string
  count: number
  onAdd?: (actId: string) => void
}

export interface ChoiceEdgeData extends Record<string, unknown> {
  choice: ChoiceOut
  outcomeKey: string
  label: string
  crossAct: boolean
  dimmed: boolean
}

export type StoryFlowNode = Node<StoryNodeData, 'story'>
export type ActFrameNode = Node<ActFrameData, 'act'>
export type ChoiceFlowEdge = Edge<ChoiceEdgeData, 'choice'>

export function buildNodes(
  graph: BookGraph,
  problems: Map<string, ProblemSummary>,
  isVisible: (n: NodeOut) => boolean,
): StoryFlowNode[] {
  const acts = sortedActs(graph)
  const colors = new Map(acts.map((a, i) => [a.id, actColor(a, i)]))
  return graph.nodes.map((n) => ({
    id: n.id,
    type: 'story',
    position: { x: n.x, y: n.y },
    width: NODE_WIDTH,
    data: {
      node: n,
      actColor: colors.get(n.act_id) ?? '#888',
      isStart: graph.book.start_node_id === n.id,
      problems: problems.get(n.id),
      dimmed: !isVisible(n),
    },
  }))
}

export function outcomeLabel(choice: ChoiceOut, key: string): string {
  const base = choice.label.trim() || (choice.kind === 'goto' ? '(no text)' : choice.kind)
  if (choice.kind === 'goto') return base
  const outcome = choice.outcomes.find((o) => o.key === key)
  if (choice.kind === 'roll' && outcome?.range_lo != null && outcome.range_hi != null) {
    const range =
      outcome.range_lo === outcome.range_hi
        ? `${outcome.range_lo}`
        : `${outcome.range_lo}–${outcome.range_hi}`
    return `${base} · ${range}`
  }
  return `${base} · ${key}`
}

export function buildEdges(graph: BookGraph, isVisible: (n: NodeOut) => boolean): ChoiceFlowEdge[] {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))
  const edges: ChoiceFlowEdge[] = []
  for (const n of graph.nodes) {
    for (const c of n.choices) {
      for (const o of c.outcomes) {
        const target = o.target_node_id ? byId.get(o.target_node_id) : undefined
        if (!target) continue
        edges.push({
          id: `${c.id}:${o.key}`,
          type: 'choice',
          source: n.id,
          target: target.id,
          data: {
            choice: c,
            outcomeKey: o.key,
            label: outcomeLabel(c, o.key),
            crossAct: target.act_id !== n.act_id,
            dimmed: !isVisible(n) && !isVisible(target),
          },
        })
      }
    }
  }
  return edges
}

interface Box {
  x: number
  y: number
  w: number
  h: number
}

export function nodeBox(n: Pick<StoryFlowNode, 'position' | 'measured'>): Box {
  return {
    x: n.position.x,
    y: n.position.y,
    w: n.measured?.width ?? NODE_WIDTH,
    h: n.measured?.height ?? NODE_HEIGHT_ESTIMATE,
  }
}

/** One frame per act around its nodes (empty acts get a small placeholder frame). */
export function computeFrames(graph: BookGraph, nodes: StoryFlowNode[]): ActFrameNode[] {
  const acts = sortedActs(graph)
  const byAct = new Map<string, StoryFlowNode[]>()
  for (const n of nodes) {
    const list = byAct.get(n.data.node.act_id) ?? []
    list.push(n)
    byAct.set(n.data.node.act_id, list)
  }
  let emptyX = 0
  for (const n of nodes) emptyX = Math.max(emptyX, nodeBox(n).x + nodeBox(n).w)
  return acts.map((act, i) => {
    const members = byAct.get(act.id) ?? []
    let box: Box
    if (members.length) {
      const boxes = members.map(nodeBox)
      const x1 = Math.min(...boxes.map((b) => b.x))
      const y1 = Math.min(...boxes.map((b) => b.y))
      const x2 = Math.max(...boxes.map((b) => b.x + b.w))
      const y2 = Math.max(...boxes.map((b) => b.y + b.h))
      box = {
        x: x1 - FRAME_PADDING,
        y: y1 - FRAME_PADDING - FRAME_HEADER,
        w: x2 - x1 + FRAME_PADDING * 2,
        h: y2 - y1 + FRAME_PADDING * 2 + FRAME_HEADER,
      }
    } else {
      emptyX += 120
      box = {
        x: emptyX,
        y: -FRAME_HEADER - FRAME_PADDING,
        w: NODE_WIDTH + FRAME_PADDING * 2,
        h: 160,
      }
      emptyX += box.w
    }
    return {
      id: `act:${act.id}`,
      type: 'act',
      position: { x: box.x, y: box.y },
      width: box.w,
      height: box.h,
      draggable: false,
      selectable: false,
      focusable: false,
      zIndex: -1,
      data: { act, color: actColor(act, i), count: members.length },
    }
  })
}

/** The act whose frame contains a point, preferring the smallest frame. */
export function actAt(frames: ActFrameNode[], x: number, y: number): string | null {
  const hits = frames.filter(
    (f) =>
      x >= f.position.x &&
      x <= f.position.x + (f.width ?? 0) &&
      y >= f.position.y &&
      y <= f.position.y + (f.height ?? 0),
  )
  hits.sort((a, b) => (a.width ?? 0) * (a.height ?? 0) - (b.width ?? 0) * (b.height ?? 0))
  return hits[0]?.data.act.id ?? null
}
