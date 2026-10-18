import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  Dices,
  Plus,
  Swords,
  Target,
  Trash2,
  Waypoints,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import {
  useCreateChoice,
  useDeleteChoice,
  useReorderChoices,
  useUpdateChoice,
} from '@/api/mutations'
import type { BookGraph, ChoiceKind, ChoiceOut, NodeOut } from '@/api/types'
import { GbxField } from '@/components/gbx/GbxField'
import { useVocabulary } from '@/components/gbx/vocabulary'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Checkbox, NumberInput, Select, TextInput } from '@/components/ui/inputs'
import { cn } from '@/lib/utils'

import { nodeOptions } from '../model'
import { useStoryStore } from '../storyStore'
import { EffectsEditor } from './EffectsEditor'

const KINDS: { value: ChoiceKind; label: string; icon: typeof Dices; hint: string }[] = [
  { value: 'goto', label: 'Go to', icon: Waypoints, hint: 'Turn to another section.' },
  {
    value: 'roll',
    label: 'Roll',
    icon: Dices,
    hint: 'Roll dice; the result picks the destination.',
  },
  { value: 'test', label: 'Test', icon: Target, hint: 'A rule-system test (e.g. Test your Luck).' },
  { value: 'combat', label: 'Combat', icon: Swords, hint: 'Fight one of this node’s encounters.' },
]

type OutcomeIn = {
  key: string
  target_node_id: string | null
  range_lo: number | null
  range_hi: number | null
}

function outcomesIn(c: ChoiceOut): OutcomeIn[] {
  return c.outcomes.map((o) => ({
    key: o.key,
    target_node_id: o.target_node_id ?? null,
    range_lo: o.range_lo ?? null,
    range_hi: o.range_hi ?? null,
  }))
}

export function ChoicesTab({ graph, node }: { graph: BookGraph; node: NodeOut }) {
  const bookId = graph.book.id
  const create = useCreateChoice(bookId)
  const reorder = useReorderChoices(bookId)
  const focusChoiceId = useStoryStore((s) => s.focusChoiceId)
  // Explicit open/closed choices; otherwise the focused choice starts open.
  const [toggled, setToggled] = useState<Map<string, boolean>>(new Map())
  const isOpen = (id: string) => toggled.get(id) ?? id === focusChoiceId
  const setOpen = (id: string, open: boolean) => setToggled((m) => new Map(m).set(id, open))

  const move = (i: number, delta: number) => {
    const ids = node.choices.map((c) => c.id)
    const [id] = ids.splice(i, 1)
    ids.splice(i + delta, 0, id!)
    reorder.mutate({ nodeId: node.id, ids })
  }

  return (
    <div className="space-y-3">
      {node.choices.length === 0 && (
        <p className="text-sm text-muted">
          No choices yet. Add one here, or drag from the node’s right handle to another node (or to
          empty space to create one).
        </p>
      )}
      {node.choices.map((c, i) => (
        <ChoiceCard
          key={c.id}
          graph={graph}
          node={node}
          choice={c}
          index={i}
          expanded={isOpen(c.id)}
          highlighted={focusChoiceId === c.id}
          onToggle={() => setOpen(c.id, !isOpen(c.id))}
          onMove={(d) => move(i, d)}
          isLast={i === node.choices.length - 1}
        />
      ))}
      <Button
        variant="outline"
        size="sm"
        onClick={() =>
          create.mutate(
            { nodeId: node.id, label: '', kind: 'goto' },
            { onSuccess: (c) => setOpen(c.id, true) },
          )
        }
      >
        <Plus className="size-4" /> Add choice
      </Button>
    </div>
  )
}

function ChoiceCard({
  graph,
  node,
  choice,
  index,
  expanded,
  highlighted,
  onToggle,
  onMove,
  isLast,
}: {
  graph: BookGraph
  node: NodeOut
  choice: ChoiceOut
  index: number
  expanded: boolean
  highlighted: boolean
  onToggle: () => void
  onMove: (delta: number) => void
  isLast: boolean
}) {
  const bookId = graph.book.id
  const update = useUpdateChoice(bookId)
  const remove = useDeleteChoice(bookId)
  const vocab = useVocabulary()
  const ref = useRef<HTMLDivElement>(null)
  const [more, setMore] = useState(
    !!(choice.min_tier || choice.print_text || choice.effects.length),
  )
  const targets = nodeOptions(graph)
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))
  const patch = (body: Omit<Parameters<typeof update.mutate>[0], 'id'>) =>
    update.mutate({ id: choice.id, ...body })
  const setOutcome = (key: string, change: Partial<OutcomeIn>) =>
    patch({ outcomes: outcomesIn(choice).map((o) => (o.key === key ? { ...o, ...change } : o)) })
  const kind = KINDS.find((k) => k.value === choice.kind)!

  useEffect(() => {
    if (highlighted) ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [highlighted])

  const summary = choice.outcomes
    .map((o) => (o.target_node_id ? byId.get(o.target_node_id)?.title : null) ?? '—')
    .join(' / ')

  return (
    <div
      ref={ref}
      className={cn(
        'rounded-lg border bg-surface',
        highlighted ? 'border-accent ring-1 ring-accent/40' : 'border-border',
      )}
    >
      <div className="flex items-center gap-1 px-2 py-1.5">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="flex min-w-0 flex-1 items-center gap-2 rounded px-1 py-0.5 text-left hover:bg-surface-2"
        >
          {expanded ? (
            <ChevronDown className="size-4 shrink-0" />
          ) : (
            <ChevronRight className="size-4 shrink-0" />
          )}
          <kind.icon className="size-3.5 shrink-0 text-muted" aria-hidden />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">
              {choice.label || <em className="text-muted">No text</em>}
            </span>
            <span className="block truncate text-xs text-muted">→ {summary}</span>
          </span>
        </button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Move choice up"
          disabled={index === 0}
          onClick={() => onMove(-1)}
        >
          <ArrowUp className="size-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Move choice down"
          disabled={isLast}
          onClick={() => onMove(1)}
        >
          <ArrowDown className="size-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Delete choice"
          onClick={() => remove.mutate(choice.id)}
        >
          <Trash2 className="size-3.5" />
        </Button>
      </div>

      {expanded && (
        <div className="space-y-4 border-t border-border px-3 py-3">
          <Field label="Choice text" hint="What the reader sees.">
            {(id) => (
              <TextInput
                id={id}
                autoFocus={!choice.label}
                value={choice.label}
                placeholder="Cross the bridge"
                onCommit={(label) => patch({ label })}
              />
            )}
          </Field>

          <div>
            <div className="mb-1 text-xs font-medium text-muted">Kind</div>
            <div role="radiogroup" aria-label="Choice kind" className="grid grid-cols-4 gap-1">
              {KINDS.map((k) => (
                <button
                  key={k.value}
                  type="button"
                  role="radio"
                  aria-checked={choice.kind === k.value}
                  title={k.hint}
                  onClick={() => choice.kind !== k.value && patch({ kind: k.value })}
                  className={cn(
                    'flex items-center justify-center gap-1 rounded-md border px-2 py-1.5 text-xs',
                    choice.kind === k.value
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-border text-muted hover:text-text',
                  )}
                >
                  <k.icon className="size-3.5" aria-hidden /> {k.label}
                </button>
              ))}
            </div>
          </div>

          {choice.kind === 'roll' && (
            <Field label="Dice">
              {() => (
                <GbxField
                  label="Dice to roll"
                  context="roll"
                  tier={choice.min_tier}
                  value={choice.dice ?? '2d6'}
                  onCommit={(dice) => patch({ dice: dice ?? '2d6' })}
                />
              )}
            </Field>
          )}
          {choice.kind === 'test' && (
            <Field label="Test">
              {(id) => (
                <Select
                  id={id}
                  value={choice.test ?? null}
                  placeholder="Choose a test…"
                  onValueChange={(test) => patch({ test })}
                  options={vocab.tests.map((t) => ({
                    value: t.key,
                    label: t.label,
                    group: t.detail,
                  }))}
                />
              )}
            </Field>
          )}
          {choice.kind === 'combat' && (
            <div className="space-y-2">
              <Field
                label="Fight"
                hint={
                  node.encounters.length
                    ? undefined
                    : 'Add an encounter in the Encounters tab first.'
                }
              >
                {(id) => (
                  <Select
                    id={id}
                    value={choice.encounter_id ?? null}
                    placeholder="Choose an encounter…"
                    onValueChange={(encounter_id) => patch({ encounter_id })}
                    options={node.encounters.map((e, i) => ({
                      value: e.id,
                      label: e.label || `Encounter ${i + 1}`,
                    }))}
                  />
                )}
              </Field>
              <Checkbox
                label="The reader may flee"
                checked={choice.flee_allowed}
                onCheckedChange={(flee_allowed) => patch({ flee_allowed })}
              />
            </div>
          )}

          <fieldset className="space-y-2">
            <legend className="mb-1 text-xs font-medium text-muted">
              {choice.kind === 'goto' ? 'Destination' : 'Outcomes'}
            </legend>
            {choice.outcomes.map((o) => (
              <div key={o.key} className="flex items-center gap-2">
                {choice.kind !== 'goto' && (
                  <span className="w-16 shrink-0 truncate text-xs font-medium text-muted capitalize">
                    {o.key}
                  </span>
                )}
                {choice.kind === 'roll' && (
                  <>
                    <NumberInput
                      aria-label={`${o.key} from`}
                      value={o.range_lo ?? null}
                      allowEmpty
                      onCommit={(range_lo) => setOutcome(o.key, { range_lo })}
                      className="w-14 px-1.5"
                    />
                    <span className="text-xs text-muted">–</span>
                    <NumberInput
                      aria-label={`${o.key} to`}
                      value={o.range_hi ?? null}
                      allowEmpty
                      onCommit={(range_hi) => setOutcome(o.key, { range_hi })}
                      className="w-14 px-1.5"
                    />
                  </>
                )}
                <Select
                  aria-label={choice.kind === 'goto' ? 'Destination node' : `${o.key} destination`}
                  value={o.target_node_id ?? null}
                  placeholder="Choose destination…"
                  onValueChange={(target_node_id) => setOutcome(o.key, { target_node_id })}
                  options={targets
                    .filter((t) => t.value !== node.id)
                    .concat(
                      targets
                        .filter((t) => t.value === node.id)
                        .map((t) => ({ ...t, label: `${t.label} — this node` })),
                    )}
                  className="min-w-0 flex-1"
                />
                {choice.kind === 'roll' && choice.outcomes.length > 1 && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Remove outcome ${o.key}`}
                    onClick={() =>
                      patch({ outcomes: outcomesIn(choice).filter((x) => x.key !== o.key) })
                    }
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                )}
              </div>
            ))}
            {choice.kind === 'roll' && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  const keys = new Set(choice.outcomes.map((o) => o.key))
                  let n = choice.outcomes.length + 1
                  while (keys.has(`r${n}`)) n++
                  patch({
                    outcomes: [
                      ...outcomesIn(choice),
                      { key: `r${n}`, target_node_id: null, range_lo: null, range_hi: null },
                    ],
                  })
                }}
              >
                <Plus className="size-4" /> Add outcome
              </Button>
            )}
          </fieldset>

          <Field label="Condition" hint={undefined}>
            {() => (
              <GbxField
                label="Condition"
                context="condition"
                tier={choice.min_tier}
                value={choice.condition ?? null}
                placeholder="e.g. has(rope) or flag(RAVEN)"
                emptyHint="Always available."
                onCommit={(condition) => patch({ condition })}
              />
            )}
          </Field>
          {choice.condition && (
            <Field label="When the condition isn’t met (digital player)">
              {(id) => (
                <Select
                  id={id}
                  value={choice.unmet_display}
                  onValueChange={(v) => v && patch({ unmet_display: v })}
                  options={[
                    { value: 'hide', label: 'Hide the choice' },
                    { value: 'show_disabled', label: 'Show it greyed out' },
                  ]}
                />
              )}
            </Field>
          )}

          <button
            type="button"
            onClick={() => setMore((m) => !m)}
            className="flex items-center gap-1 text-xs font-medium text-muted hover:text-text"
            aria-expanded={more}
          >
            {more ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}{' '}
            Tier, print text & effects
          </button>
          {more && (
            <div className="space-y-4">
              <Field label="Only from tier">
                {(id) => (
                  <Select
                    id={id}
                    value={choice.min_tier ?? null}
                    placeholder="All tiers"
                    onValueChange={(min_tier) => patch({ min_tier })}
                    options={vocab.tiers.map((t) => ({ value: t.key, label: `${t.label} and up` }))}
                  />
                )}
              </Field>
              <Field
                label="Print text override"
                hint="Replaces the generated “If you…, turn to N” wording."
              >
                {(id) => (
                  <TextInput
                    id={id}
                    value={choice.print_text ?? ''}
                    onCommit={(t) => patch({ print_text: t || null })}
                  />
                )}
              </Field>
              <Field label="Effects when taken">
                {() => (
                  <EffectsEditor
                    value={choice.effects}
                    tier={choice.min_tier}
                    onChange={(effects) => patch({ effects })}
                    emptyText="Taking this choice changes nothing."
                  />
                )}
              </Field>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
