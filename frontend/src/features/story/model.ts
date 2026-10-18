/** Pure helpers over the book graph (no React). */
import type { ActOut, BookGraph, NodeOut, ProblemOut } from '@/api/types'

import type { StoryFilters } from './storyStore'

/** Distinct, theme-friendly act colours (used when an act has no colour set). */
export const ACT_PALETTE = [
  '#7c6ae6',
  '#2f9e8f',
  '#d9822b',
  '#c2549b',
  '#3b82c4',
  '#8a9a3a',
  '#b5523b',
  '#5e6ad2',
]

export function sortedActs(graph: BookGraph): ActOut[] {
  return [...graph.acts].sort((a, b) => a.position - b.position)
}

export function actColor(act: ActOut, index: number): string {
  return act.color || ACT_PALETTE[index % ACT_PALETTE.length]!
}

export interface ProblemSummary {
  errors: number
  warnings: number
  messages: string[]
}

export function problemsByNode(problems: ProblemOut[] | undefined): Map<string, ProblemSummary> {
  const out = new Map<string, ProblemSummary>()
  for (const p of problems ?? []) {
    if (!p.node_id) continue
    const s = out.get(p.node_id) ?? { errors: 0, warnings: 0, messages: [] }
    if (p.severity === 'error') s.errors++
    else if (p.severity === 'warning') s.warnings++
    s.messages.push(p.message)
    out.set(p.node_id, s)
  }
  return out
}

export function matchesSearch(node: NodeOut, q: string): boolean {
  const needle = q.trim().toLowerCase()
  if (!needle) return true
  return [node.title, node.key, node.beat_notes, node.summary].some((t) =>
    t.toLowerCase().includes(needle),
  )
}

export function matchesFilters(
  node: NodeOut,
  f: StoryFilters,
  problems: Map<string, ProblemSummary>,
): boolean {
  if (f.problems && !problems.has(node.id)) return false
  if (f.gated && !node.choices.some((c) => c.condition)) return false
  if (f.encounters && node.encounters.length === 0) return false
  if (f.items && node.items.length === 0 && !node.is_shop) return false
  if (f.endings && !node.ending_kind) return false
  return true
}

export function anyFilter(f: StoryFilters): boolean {
  return Object.values(f).some(Boolean)
}

/** Select options for picking a node, grouped by act. */
export function nodeOptions(graph: BookGraph) {
  const acts = new Map(graph.acts.map((a) => [a.id, a]))
  return [...graph.nodes]
    .sort((a, b) => {
      const pa = acts.get(a.act_id)?.position ?? 0
      const pb = acts.get(b.act_id)?.position ?? 0
      return pa - pb || a.title.localeCompare(b.title)
    })
    .map((n) => ({ value: n.id, label: `${n.title} (${n.key})`, group: acts.get(n.act_id)?.title }))
}
