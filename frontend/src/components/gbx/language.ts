import {
  autocompletion,
  type CompletionContext,
  type CompletionResult,
} from '@codemirror/autocomplete'
import { HighlightStyle, StreamLanguage, syntaxHighlighting } from '@codemirror/language'
import { tags as t } from '@lezer/highlight'

import type { GbxContext } from '@/api/types'

import { CONTEXT_VARIABLES, FUNCTIONS, type VocabEntry, type Vocabulary } from './vocabulary'

const KEYWORDS = new Set(['and', 'or', 'not', 'true', 'false'])
const FUNCS = new Set(FUNCTIONS.map((f) => f.key))

export const gbxLanguage = StreamLanguage.define<null>({
  name: 'gbx',
  token(stream) {
    if (stream.eatSpace()) return null
    if (stream.match(/^\d*d\d+(?![A-Za-z0-9_])/)) return 'atom'
    if (stream.match(/^\d+/)) return 'number'
    const word = stream.match(/^[A-Za-z_][A-Za-z0-9_]*/) as RegExpMatchArray | null
    if (word) {
      const w = word[0]
      if (KEYWORDS.has(w)) return 'keyword'
      if (FUNCS.has(w) && stream.peek() === '(') return 'function'
      if (w === 'player' || w === 'enemy' || w === 'attacker' || w === 'target') return 'namespace'
      return /^[A-Z][A-Z0-9_]*$/.test(w) ? 'constant' : 'variableName'
    }
    stream.next()
    return 'operator'
  },
  tokenTable: {
    atom: t.atom,
    function: t.function(t.variableName),
    namespace: t.namespace,
    constant: t.constant(t.variableName),
  },
})

export const gbxHighlight = syntaxHighlighting(
  HighlightStyle.define([
    { tag: t.number, color: 'var(--info)' },
    { tag: t.atom, color: 'var(--accent)', fontWeight: '600' },
    { tag: t.keyword, color: 'var(--accent)' },
    { tag: t.function(t.variableName), color: 'var(--success)' },
    { tag: t.namespace, color: 'var(--muted)' },
    { tag: t.constant(t.variableName), color: 'var(--warning)' },
    { tag: t.operator, color: 'var(--muted)' },
  ]),
)

function options(entries: VocabEntry[], type: string) {
  return entries.map((e) => ({
    label: e.key,
    detail: e.label === e.key ? e.detail : e.label,
    type,
  }))
}

export function gbxCompletions(getVocab: () => Vocabulary, context: GbxContext) {
  return autocompletion({
    activateOnTyping: true,
    override: [
      (cx: CompletionContext): CompletionResult | null => {
        const vocab = getVocab()
        const before = cx.state.sliceDoc(0, cx.pos)
        const inCall = /([a-z]+)\(\s*([A-Za-z0-9_]*)$/.exec(before)
        if (inCall) {
          const from = cx.pos - inCall[2]!.length
          const fn = inCall[1]!
          const map: Record<string, ReturnType<typeof options>> = {
            has: options(vocab.items, 'variable'),
            count: options(vocab.items, 'variable'),
            equipped: options(vocab.items, 'variable'),
            flag: options(vocab.flags, 'constant'),
            skill: options(vocab.skills, 'constant'),
            class: options(vocab.classes, 'type'),
            visits: options(vocab.nodes, 'variable'),
          }
          if (map[fn]) return { from, options: map[fn]!, validFor: /^[A-Za-z0-9_]*$/ }
        }
        const attr = /\b(player|enemy|attacker|target)\.([A-Za-z0-9_]*)$/.exec(before)
        if (attr) {
          return {
            from: cx.pos - attr[2]!.length,
            options: options(vocab.stats, 'property'),
            validFor: /^[A-Za-z0-9_]*$/,
          }
        }
        const word = cx.matchBefore(/[A-Za-z_][A-Za-z0-9_]*/)
        if (!word && !cx.explicit) return null
        const vars = (CONTEXT_VARIABLES[context] ?? []).map((v) => ({ label: v, type: 'variable' }))
        return {
          from: word?.from ?? cx.pos,
          options: [
            ...FUNCTIONS.map((f) => ({
              label: f.key,
              detail: f.label,
              info: f.detail,
              type: 'function',
              apply: `${f.key}(`,
            })),
            ...options(vocab.stats, 'property'),
            { label: 'tier', type: 'keyword', detail: 'the tier being played' },
            ...options(vocab.tiers, 'enum'),
            ...vars,
            ...['and', 'or', 'not'].map((k) => ({ label: k, type: 'keyword' })),
          ],
          validFor: /^[A-Za-z0-9_]*$/,
        }
      },
    ],
  })
}
