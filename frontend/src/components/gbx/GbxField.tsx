import { closeBrackets } from '@codemirror/autocomplete'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { type Diagnostic as CmDiagnostic, setDiagnostics } from '@codemirror/lint'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, placeholder as cmPlaceholder } from '@codemirror/view'
import { useEffect, useId, useRef, useState } from 'react'

import { api, unwrap } from '@/api/client'
import type { GbxContext } from '@/api/types'
import { cn } from '@/lib/utils'

import { gbxCompletions, gbxHighlight, gbxLanguage } from './language'
import { useVocabulary, type Vocabulary } from './vocabulary'

const CHECK_DELAY_MS = 300

function runCheck(body: {
  source: string
  context: GbxContext
  book_id: string
  tier: string | null
}) {
  return unwrap(api.POST('/api/gbx/check', { body }))
}
type CheckResult = Awaited<ReturnType<typeof runCheck>>

const theme = EditorView.theme({
  '&': {
    fontSize: '13px',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    background: 'var(--bg)',
  },
  '&.cm-focused': { outline: 'none', borderColor: 'var(--accent)' },
  '.cm-content': { fontFamily: 'var(--font-mono)', padding: '5px 0', caretColor: 'var(--text)' },
  '.cm-line': { padding: '0 8px' },
  '.cm-scroller': { overflow: 'hidden' },
  '.cm-placeholder': { color: 'var(--muted)', opacity: '0.7' },
  '.cm-tooltip': {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: '6px',
  },
  '.cm-tooltip-autocomplete > ul > li[aria-selected]': {
    background: 'var(--surface-2)',
    color: 'var(--text)',
  },
  '.cm-completionDetail': { color: 'var(--muted)', fontStyle: 'normal', marginLeft: '8px' },
  '.cm-lintRange-error': {
    backgroundImage: 'none',
    textDecoration: 'wavy underline var(--danger)',
  },
  '.cm-lintRange-warning': {
    backgroundImage: 'none',
    textDecoration: 'wavy underline var(--warning)',
  },
})

export interface GbxFieldProps {
  value: string | null
  onCommit: (value: string | null) => void
  context: GbxContext
  tier?: string | null
  placeholder?: string
  label: string
  className?: string
  /** Show "Always available" etc. when empty (conditions). */
  emptyHint?: string
}

/**
 * Single-line gbx editor: highlighting, autocomplete from the book's vocabulary,
 * live server checks (diagnostics + English + odds). Commits on blur/Enter.
 */
export function GbxField({
  value,
  onCommit,
  context,
  tier,
  placeholder,
  label,
  className,
  emptyHint,
}: GbxFieldProps) {
  const vocab = useVocabulary()
  const vocabRef = useRef<Vocabulary>(vocab)
  vocabRef.current = vocab
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const committed = useRef(value ?? '')
  const onCommitRef = useRef(onCommit)
  onCommitRef.current = onCommit
  const [check, setCheck] = useState<CheckResult | null>(null)
  const [text, setText] = useState(value ?? '')
  const describedBy = useId()

  // Create the editor once.
  useEffect(() => {
    const commit = () => {
      const doc = view.current?.state.doc.toString().trim() ?? ''
      if (doc !== committed.current) {
        committed.current = doc
        onCommitRef.current(doc === '' ? null : doc)
      }
    }
    const v = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: value ?? '',
        extensions: [
          history(),
          closeBrackets(),
          gbxLanguage,
          gbxHighlight,
          gbxCompletions(() => vocabRef.current, context),
          cmPlaceholder(placeholder ?? ''),
          theme,
          EditorState.transactionFilter.of((tr) => (tr.newDoc.lines > 1 ? [] : tr)),
          keymap.of([
            {
              key: 'Enter',
              run: (ed) => {
                ed.contentDOM.blur()
                return true
              },
            },
            {
              key: 'Escape',
              run: (ed) => {
                ed.dispatch({
                  changes: { from: 0, to: ed.state.doc.length, insert: committed.current },
                })
                ed.contentDOM.blur()
                return true
              },
            },
            ...defaultKeymap,
            ...historyKeymap,
          ]),
          EditorView.updateListener.of((u) => {
            if (u.docChanged) setText(u.state.doc.toString())
          }),
          EditorView.domEventHandlers({ blur: () => commit() }),
          EditorView.contentAttributes.of({ 'aria-label': label, 'aria-describedby': describedBy }),
        ],
      }),
    })
    view.current = v
    return () => {
      commit()
      v.destroy()
      view.current = null
    }
    // The editor is configured once; value/context changes are synced below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Follow server value when not focused.
  useEffect(() => {
    const v = view.current
    if (!v || v.hasFocus) return
    const next = value ?? ''
    committed.current = next
    if (v.state.doc.toString() !== next) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: next } })
    }
  }, [value])

  // Debounced server check.
  useEffect(() => {
    const source = text.trim()
    if (!source || !vocab.bookId) {
      setCheck(null)
      view.current?.dispatch(setDiagnostics(view.current.state, []))
      return
    }
    let cancelled = false
    const timer = setTimeout(async () => {
      try {
        const res = await runCheck({
          source: text,
          context,
          book_id: vocab.bookId,
          tier: tier ?? null,
        })
        if (cancelled) return
        setCheck(res)
        const v = view.current
        if (v && v.state.doc.toString() === text) {
          const len = v.state.doc.length
          const diags: CmDiagnostic[] = res.diagnostics
            .filter((d) => d.severity !== 'info')
            .map((d) => ({
              from: Math.min(d.start, len),
              to: Math.min(Math.max(d.end, d.start + 1), len),
              severity: d.severity === 'error' ? 'error' : 'warning',
              message: d.message,
            }))
          v.dispatch(setDiagnostics(v.state, diags))
        }
      } catch {
        // Offline or server error: keep the last result.
      }
    }, CHECK_DELAY_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [text, context, tier, vocab.bookId])

  const firstError = check?.diagnostics.find((d) => d.severity === 'error')
  const firstWarning = check?.diagnostics.find((d) => d.severity !== 'error')
  const odds = check?.distribution ? summariseOdds(check.distribution) : null

  return (
    <div className={cn('space-y-1', className)}>
      <div ref={host} />
      <p id={describedBy} className="min-h-4 text-xs leading-snug" aria-live="polite">
        {!text.trim() ? (
          emptyHint && <span className="text-muted">{emptyHint}</span>
        ) : firstError ? (
          <span className="text-danger">{firstError.message}</span>
        ) : check?.english ? (
          <span className="text-muted">
            “{check.english}”{check.range && ` · ${check.range[0]}–${check.range[1]}`}
            {odds && ` · ${odds}`}
            {firstWarning && <span className="block text-warning">{firstWarning.message}</span>}
          </span>
        ) : null}
      </p>
    </div>
  )
}

function summariseOdds(dist: Record<string, number>): string {
  const entries = Object.entries(dist).map(([k, p]) => [Number(k), p] as const)
  const mode = entries.reduce((a, b) => (b[1] > a[1] ? b : a))
  return `most likely ${mode[0]} (${Math.round(mode[1] * 100)}%)`
}
