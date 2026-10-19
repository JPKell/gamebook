import { useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown, ChevronRight, Sparkles, X } from 'lucide-react'
import { useState } from 'react'

import type { BookGraph } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Select } from '@/components/ui/inputs'
import {
  type SuggestionPayload,
  useAcceptSuggestion,
  useAssistItems,
  useRejectSuggestion,
  useSuggest,
} from '@/features/assist/api'
import { isActive, useJobStream } from '@/features/playtest/api'

import { isOpenSuggestion as open } from './useSuggestionGhosts'

/** Ask for suggestions and review them choice by choice. */
export function SuggestionsBar({ graph }: { graph: BookGraph }) {
  const bookId = graph.book.id
  const items = useAssistItems(bookId, 'suggestion')
  const accept = useAcceptSuggestion(bookId)
  const reject = useRejectSuggestion(bookId)
  const [expanded, setExpanded] = useState(true)
  const openItems = (items.data ?? []).filter(open)
  const keys = new Map(graph.nodes.map((n) => [n.key, n.title]))

  return (
    <>
      {openItems.length > 0 && (
        <section
          aria-label="Suggestions"
          className="border-b border-border bg-accent/5 px-3 py-1.5 text-xs"
        >
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-expanded={expanded}
              onClick={() => setExpanded((e) => !e)}
              className="flex items-center gap-1 font-medium"
            >
              {expanded ? (
                <ChevronDown className="size-3.5" />
              ) : (
                <ChevronRight className="size-3.5" />
              )}
              <Sparkles className="size-3.5 text-accent" aria-hidden /> Suggested sections (dashed
              on the canvas)
            </button>
            <div className="ml-auto flex gap-1">
              <Button
                size="sm"
                onClick={() => openItems.forEach((i) => accept.mutate({ id: i.id }))}
                disabled={accept.isPending}
              >
                <Check className="size-3.5" /> Add all
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => openItems.forEach((i) => reject.mutate({ id: i.id }))}
                disabled={reject.isPending}
              >
                <X className="size-3.5" /> Dismiss all
              </Button>
            </div>
          </div>
          {expanded &&
            openItems.map((item) => {
              const p = item.payload as unknown as SuggestionPayload
              const name = (k: string) =>
                keys.get(k) ?? p.nodes.find((n) => n.ref === k)?.title ?? k
              return (
                <div key={item.id} className="space-y-1 py-1">
                  {p.rationale && <p className="text-muted">{p.rationale}</p>}
                  <ul className="space-y-0.5">
                    {p.choices.map((c, i) =>
                      c.status === 'pending' ? (
                        <li key={i} className="flex items-center gap-2">
                          <span className="min-w-0 flex-1 truncate">
                            Choice <span className="font-medium">“{c.label || 'Continue'}”</span>:{' '}
                            {name(c.from)} → {name(c.to)}
                          </span>
                          <Button
                            size="sm"
                            variant="outline"
                            aria-label={`Add choice “${c.label || 'Continue'}”: ${name(c.from)} → ${name(c.to)}`}
                            onClick={() => accept.mutate({ id: item.id, choices: [i] })}
                          >
                            Add
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-label={`Dismiss choice “${c.label || 'Continue'}”: ${name(c.from)} → ${name(c.to)}`}
                            onClick={() => reject.mutate({ id: item.id, choices: [i] })}
                          >
                            Dismiss
                          </Button>
                        </li>
                      ) : null,
                    )}
                  </ul>
                </div>
              )
            })}
        </section>
      )}
    </>
  )
}

function suggestResult(result: unknown) {
  const r = (result ?? {}) as { nodes?: number; choices?: number; item_id?: string | null }
  if (!r.item_id) return 'Nothing new to suggest for this act.'
  const parts = [
    r.nodes ? `${r.nodes} section(s)` : null,
    r.choices ? `${r.choices} choice(s)` : null,
  ].filter(Boolean)
  return `Suggested ${parts.join(' and ') || 'nothing'}; they're on the canvas.`
}

export function SuggestDialog({
  graph,
  open: isOpen,
  onOpenChange,
}: {
  graph: BookGraph
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const bookId = graph.book.id
  const qc = useQueryClient()
  const suggest = useSuggest()
  const job = useJobStream(
    suggest.data?.id,
    () => void qc.invalidateQueries({ queryKey: ['book', bookId] }),
  )
  const [actId, setActId] = useState<string | null>(null)
  const [notes, setNotes] = useState('')
  const act = actId ?? graph.acts[0]?.id ?? null
  return (
    <Dialog
      open={isOpen}
      onOpenChange={onOpenChange}
      title="Suggest sections"
      description="The suggester reads the act's outline and existing sections, and proposes new sections and choices for beats that have none yet. Nothing changes until you add them."
      footer={
        <Button
          disabled={!act || suggest.isPending || isActive(job?.status)}
          onClick={() => act && suggest.mutate({ actId: act, notes })}
        >
          <Sparkles className="size-4" /> {isActive(job?.status) ? 'Thinking…' : 'Suggest'}
        </Button>
      }
    >
      <div className="space-y-3">
        <Field label="Act">
          {(id) => (
            <Select
              id={id}
              value={act}
              options={graph.acts.map((a) => ({ value: a.id, label: a.title }))}
              onValueChange={setActId}
            />
          )}
        </Field>
        <Field label="Notes for the suggester">
          {(id) => (
            <textarea
              id={id}
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. add a moral dilemma before the ending"
              className="w-full rounded-md border border-border bg-bg p-2 text-sm"
            />
          )}
        </Field>
        {job && !isActive(job.status) && (
          <p
            role="status"
            className={job.status === 'done' ? 'text-sm text-success' : 'text-sm text-danger'}
          >
            {job.status === 'done' ? suggestResult(job.result) : (job.error ?? job.status)}
          </p>
        )}
      </div>
    </Dialog>
  )
}
