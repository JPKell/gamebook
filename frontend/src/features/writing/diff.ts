export type Piece = { op: 'eq' | 'add' | 'del'; text: string }

const tokens = (s: string) => s.split(/(\s+)/).filter((t) => t !== '')

/** Longest-common-subsequence word diff (whitespace kept as its own tokens). */
function lcs(a: string[], b: string[]): Piece[] {
  const n = a.length
  const m = b.length
  const dp = new Uint32Array((n + 1) * (m + 1))
  const at = (i: number, j: number) => i * (m + 1) + j
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[at(i, j)] =
        a[i] === b[j] ? dp[at(i + 1, j + 1)]! + 1 : Math.max(dp[at(i + 1, j)]!, dp[at(i, j + 1)]!)
  const out: Piece[] = []
  const push = (op: Piece['op'], text: string) => {
    const last = out[out.length - 1]
    if (last && last.op === op) last.text += text
    else out.push({ op, text })
  }
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      push('eq', a[i]!)
      i++
      j++
    } else if (dp[at(i + 1, j)]! >= dp[at(i, j + 1)]!) push('del', a[i++]!)
    else push('add', b[j++]!)
  }
  while (i < n) push('del', a[i++]!)
  while (j < m) push('add', b[j++]!)
  return out
}

/** Word diff from ``before`` to ``after``; very long texts fall back to paragraphs. */
export function diffWords(before: string, after: string): Piece[] {
  const a = tokens(before)
  const b = tokens(after)
  if (a.length * b.length <= 4_000_000) return lcs(a, b)
  return lcs(before.split(/(\n\n+)/), after.split(/(\n\n+)/))
}
