/** Wiki mentions: [[key]], [[character:key]] / [[lore:key]], optional |label (backend: refs.MENTION). */
export const MENTION =
  /\[\[(?:(character|lore):)?([A-Za-z][A-Za-z0-9_]{0,63})(?:\|([^\]\n]*))?\]\]/g

export interface MentionTarget {
  kind: 'character' | 'lore'
  id: string
  key: string
  name: string
}

export type Segment =
  { text: string } | { mention: string; label: string; target: MentionTarget | null }

/** Split text into plain runs and resolved (or broken) mentions. Characters win bare-key ties. */
export function segments(text: string, targets: MentionTarget[]): Segment[] {
  const out: Segment[] = []
  let last = 0
  for (const m of text.matchAll(MENTION)) {
    const [whole, kind, key, label] = m
    if (m.index > last) out.push({ text: text.slice(last, m.index) })
    const target =
      targets.find((t) => t.key === key && (kind ? t.kind === kind : t.kind === 'character')) ??
      (kind ? null : (targets.find((t) => t.key === key) ?? null))
    out.push({ mention: whole, label: label?.trim() || target?.name || key!, target })
    last = m.index + whole.length
  }
  if (last < text.length) out.push({ text: text.slice(last) })
  return out
}
