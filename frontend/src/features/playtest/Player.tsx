import {
  Bug,
  CircleAlert,
  Dices,
  Flag,
  RotateCcw,
  Shuffle,
  Skull,
  Swords,
  Trophy,
  Undo2,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { useBookGraph } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { NumberInput, Select, TextInput } from '@/components/ui/inputs'
import { cn } from '@/lib/utils'

import { type PlayIn, type PlayInput, type PlayOut, usePlay } from './api'
import { CodexPanel, MapPanel, SceneArt } from './PlayerExtras'

type Tier = { key: string; label: string }

interface Session {
  tier: string
  seed: number
  character_class: string | null
  inputs: PlayInput[]
}

const storageKey = (bookId: string) => `gamebook:play:${bookId}`

function load(bookId: string): Session | null {
  try {
    const raw = localStorage.getItem(storageKey(bookId))
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

function save(bookId: string, s: Session) {
  try {
    localStorage.setItem(storageKey(bookId), JSON.stringify(s))
  } catch {
    // Private mode / full storage: the session just won't survive a reload.
  }
}

const MAX_SEED = 2 ** 31 - 1
const newSeed = () => Math.floor(Math.random() * 1_000_000)

/** The reader's view of a book: play it, with a debug drawer for the author. */
export function Player({
  bookId,
  tiers,
  defaultTier,
}: {
  bookId: string
  tiers: Tier[]
  defaultTier: string
}) {
  const [session, setSession] = useState<Session>(
    () => load(bookId) ?? { tier: defaultTier, seed: newSeed(), character_class: null, inputs: [] },
  )
  useEffect(() => save(bookId, session), [bookId, session])
  const tier = tiers.some((t) => t.key === session.tier) ? session.tier : defaultTier

  const body: PlayIn = {
    tier,
    seed: session.seed,
    character_class: session.character_class,
    inputs: session.inputs,
  }
  const play = usePlay(bookId, body)
  const view = play.data

  const push = (input: PlayInput) => setSession((s) => ({ ...s, inputs: [...s.inputs, input] }))
  const back = () => setSession((s) => ({ ...s, inputs: s.inputs.slice(0, -1) }))
  const restart = (patch: Partial<Session> = {}) =>
    setSession((s) => ({ ...s, inputs: [], seed: newSeed(), ...patch }))
  // "What happened" shows everything since the last real move (debug inputs alone don't count).
  const applied = view?.applied ?? 0
  let lastMove = -1
  for (let i = applied - 1; i >= 0; i--)
    if (session.inputs[i]?.kind === 'action' || session.inputs[i]?.kind === 'jump') {
      lastMove = i
      break
    }
  const dropRest = () =>
    view && setSession((s) => ({ ...s, inputs: s.inputs.slice(0, view.applied) }))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Tier">
          {(id) => (
            <Select
              id={id}
              value={tier}
              options={tiers.map((t) => ({ value: t.key, label: t.label }))}
              onValueChange={(t) => t && restart({ tier: t, character_class: null })}
              className="w-36"
            />
          )}
        </Field>
        {view && view.classes.length > 0 && (
          <Field label="Class">
            {(id) => (
              <Select
                id={id}
                value={session.character_class ?? view.character_class}
                options={view.classes.map((c) => ({ value: c.key, label: c.label }))}
                onValueChange={(c) => restart({ character_class: c, seed: session.seed })}
                className="w-40"
              />
            )}
          </Field>
        )}
        <Field label="Seed" hint="Same seed, same dice">
          {(id) => (
            <NumberInput
              id={id}
              className="w-28"
              min={0}
              value={session.seed}
              max={MAX_SEED}
              onCommit={(seed) =>
                seed !== null && restart({ seed: Math.min(MAX_SEED, Math.max(0, seed)) })
              }
            />
          )}
        </Field>
        <div className="ml-auto flex gap-2 pb-5">
          <Button variant="outline" size="sm" onClick={back} disabled={!session.inputs.length}>
            <Undo2 className="size-4" /> Back
          </Button>
          <Button variant="outline" size="sm" onClick={() => restart({ seed: session.seed })}>
            <RotateCcw className="size-4" /> Restart
          </Button>
          <Button size="sm" onClick={() => restart({ character_class: null })}>
            <Shuffle className="size-4" /> New character
          </Button>
        </div>
      </div>

      {play.isError && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-lg border border-danger/40 bg-danger/8 p-3 text-sm text-danger"
        >
          <span className="flex-1">{play.error.message}</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              setSession({ tier: defaultTier, seed: newSeed(), character_class: null, inputs: [] })
            }
          >
            Reset session
          </Button>
        </div>
      )}
      {view?.error && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-lg border border-warning/40 bg-warning/8 p-3 text-sm"
        >
          <CircleAlert className="size-4 text-warning" aria-hidden />
          <span className="flex-1">The book changed since these moves were made. {view.error}</span>
          <Button size="sm" variant="outline" onClick={dropRest}>
            Continue from here
          </Button>
        </div>
      )}

      {view && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            <Scene view={view} bookId={bookId} turn={lastMove} />
            {view.combat && <CombatPanel combat={view.combat} />}
            <Actions
              view={view}
              onAct={(a) => push({ kind: 'action', type: a.type as never, target: a.target })}
              onRestart={() => restart()}
              busy={play.isFetching}
            />
            <Debug bookId={bookId} view={view} onInput={push} />
          </div>
          <aside className="space-y-4">
            <Sheet view={view} />
            <MapPanel maps={view.maps} />
            <CodexPanel bookId={bookId} view={view} />
            <DiceLog view={view} />
          </aside>
        </div>
      )}
    </div>
  )
}

const ENDINGS: Record<string, { label: string; icon: typeof Trophy; tone: string }> = {
  victory: { label: 'Victory', icon: Trophy, tone: 'text-success border-success/40 bg-success/8' },
  death: { label: 'You died', icon: Skull, tone: 'text-danger border-danger/40 bg-danger/8' },
  defeated: { label: 'Defeated', icon: Skull, tone: 'text-danger border-danger/40 bg-danger/8' },
  dead_end: { label: 'Dead end', icon: Flag, tone: 'text-warning border-warning/40 bg-warning/8' },
  stuck: { label: 'Stuck', icon: CircleAlert, tone: 'text-warning border-warning/40 bg-warning/8' },
}

/** Where the reader is: node text (beat notes until prose exists) and what just happened. */
export function Scene({ view, bookId, turn }: { view: PlayOut; bookId: string; turn: number }) {
  const lines = view.events.filter(
    (e) => e.turn >= turn && e.text && e.type !== 'roll' && e.type !== 'game_over',
  )
  const ending = view.ended ? ENDINGS[view.ended] : null
  const node = view.node
  return (
    <section
      aria-label="Scene"
      className="space-y-3 rounded-xl border border-border bg-surface p-5"
    >
      {node && (
        <header className="flex flex-wrap items-baseline gap-2">
          {node.act_title && (
            <span className="text-xs tracking-wide text-muted uppercase">{node.act_title}</span>
          )}
          <h2 className="text-xl font-semibold">{node.title}</h2>
          {node.variant_label && node.variant_label !== 'Default' && (
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-muted">
              {node.variant_label}
            </span>
          )}
          <Link
            to={`/story/${bookId}?node=${node.id}`}
            className="ml-auto text-xs text-accent hover:underline"
          >
            Open in story
          </Link>
        </header>
      )}
      <SceneArt art={view.art} />
      {node &&
        (node.prose ? (
          <section aria-label="Prose" className="space-y-3 font-serif text-[16px] leading-relaxed">
            {node.prose
              .split(/\n{2,}/)
              .filter((para) => para.trim())
              .map((para, i) => (
                <p key={i} className="whitespace-pre-wrap">
                  {para}
                </p>
              ))}
          </section>
        ) : node.beat_notes ? (
          <div className="space-y-1">
            <p className="text-[11px] font-medium tracking-wide text-muted uppercase">
              Beat notes (no prose yet)
            </p>
            <p className="whitespace-pre-wrap">{node.beat_notes}</p>
          </div>
        ) : (
          <p className="text-sm text-muted italic">No prose or beat notes for this section yet.</p>
        ))}
      {lines.length > 0 && (
        <ul
          aria-label="What happened"
          className="space-y-1 rounded-lg bg-surface-2 p-3 font-mono text-[13px]"
        >
          {lines.map((e, i) => (
            <li
              key={i}
              className={cn(
                e.type === 'error' && 'text-danger',
                e.type === 'debug' && 'text-muted',
              )}
            >
              {e.text}
            </li>
          ))}
        </ul>
      )}
      {ending && (
        <div
          role="status"
          className={cn('flex items-center gap-2 rounded-lg border p-3 font-medium', ending.tone)}
        >
          <ending.icon className="size-5" aria-hidden />
          {ending.label}
          {view.events.findLast((e) => e.type === 'game_over')?.data.reason
            ? ` — ${String(view.events.findLast((e) => e.type === 'game_over')?.data.reason)}`
            : null}
        </div>
      )}
    </section>
  )
}

function CombatPanel({ combat }: { combat: NonNullable<PlayOut['combat']> }) {
  return (
    <section
      aria-label="Combat"
      className="space-y-2 rounded-xl border border-danger/30 bg-surface p-4"
    >
      <h3 className="flex items-center gap-2 text-sm font-semibold">
        <Swords className="size-4 text-danger" aria-hidden /> Combat · round {combat.round}
      </h3>
      <ul className="grid gap-2 sm:grid-cols-2">
        {combat.enemies.map((e) => (
          <li key={e.key} className="rounded-lg border border-border p-2 text-sm">
            <div className="font-medium">
              {e.name} <span className="text-xs text-muted">level {e.level}</span>
            </div>
            <div className="text-xs text-muted tabular-nums">
              {Object.entries(e.stats)
                .map(([k, v]) => `${k} ${v}`)
                .join(' · ')}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Actions({
  view,
  onAct,
  onRestart,
  busy,
}: {
  view: PlayOut
  onAct: (a: PlayOut['actions'][number]) => void
  onRestart: () => void
  /** A move is being replayed: don't accept another click on stale options. */
  busy: boolean
}) {
  if (view.ended)
    return (
      <Button onClick={onRestart}>
        <Shuffle className="size-4" /> Play again
      </Button>
    )
  const choices = view.actions.filter((a) => ['choose', 'attack', 'flee'].includes(a.type))
  const other = view.actions.filter((a) => !['choose', 'attack', 'flee'].includes(a.type))
  return (
    <section aria-label="Choices" className="space-y-3">
      <ol className="space-y-2">
        {choices.map((a, i) => (
          <li key={`${a.type}:${a.target}`}>
            <button
              type="button"
              disabled={!a.enabled || busy}
              onClick={() => onAct(a)}
              className="flex w-full items-center gap-3 rounded-lg border border-border bg-surface px-4 py-2.5 text-left hover:border-accent hover:bg-accent/6 disabled:cursor-not-allowed disabled:opacity-55 disabled:hover:border-border disabled:hover:bg-surface"
            >
              <span className="w-5 text-sm text-muted tabular-nums">{i + 1}.</span>
              <span className="flex-1 font-medium">{a.label || '(unlabelled choice)'}</span>
              {a.reason && <span className="text-xs text-muted">{a.reason}</span>}
            </button>
          </li>
        ))}
      </ol>
      {other.length > 0 && (
        <div className="flex flex-wrap gap-2" aria-label="Items and shop" role="group">
          {other.map((a) => (
            <Button
              key={`${a.type}:${a.target}`}
              size="sm"
              variant="outline"
              disabled={!a.enabled || busy}
              title={a.reason ?? undefined}
              onClick={() => onAct(a)}
            >
              {a.label}
              {a.reason && <span className="text-muted">({a.reason})</span>}
            </Button>
          ))}
        </div>
      )}
    </section>
  )
}

export function Sheet({ view }: { view: PlayOut }) {
  return (
    <section
      aria-label="Adventure sheet"
      className="space-y-3 rounded-xl border border-border bg-surface p-4 text-sm"
    >
      <h3 className="font-semibold">Adventure sheet</h3>
      <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
        {view.stats.map((s) => (
          <div key={s.key} className="contents">
            <dt className="text-muted">{s.label}</dt>
            <dd className="text-right tabular-nums">
              <span className="font-medium">{s.effective}</span>
              {s.max != null && <span className="text-muted"> / {s.max}</span>}
              {s.effective !== s.value && (
                <span className="ml-1 text-xs text-success" title="Item bonus">
                  ({s.effective > s.value ? '+' : ''}
                  {s.effective - s.value})
                </span>
              )}
            </dd>
          </div>
        ))}
      </dl>
      {view.character_class && (
        <p>
          <span className="text-muted">Class:</span>{' '}
          {view.classes.find((c) => c.key === view.character_class)?.label ?? view.character_class}
        </p>
      )}
      {view.skills.length > 0 && (
        <p>
          <span className="text-muted">Skills:</span> {view.skills.map((s) => s.label).join(', ')}
        </p>
      )}
      <div>
        <h4 className="mb-1 text-xs font-medium text-muted uppercase">Inventory</h4>
        {view.items.length === 0 ? (
          <p className="text-muted">Empty.</p>
        ) : (
          <ul className="space-y-0.5">
            {view.items.map((i) => (
              <li key={i.key} className="flex gap-2">
                <span className="flex-1">{i.name}</span>
                {i.equipped && (
                  <span className="rounded bg-accent/12 px-1.5 text-xs text-accent">equipped</span>
                )}
                {i.count > 1 && <span className="tabular-nums text-muted">×{i.count}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
      {view.flags.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-medium text-muted uppercase">Codewords</h4>
          <p className="font-mono text-xs">{view.flags.join(' · ')}</p>
        </div>
      )}
    </section>
  )
}

function DiceLog({ view }: { view: PlayOut }) {
  const rolls = view.events
    .filter((e) => e.type === 'roll' || e.type === 'combat_round')
    .slice(-40)
    .reverse()
  return (
    <section
      aria-label="Dice log"
      className="space-y-2 rounded-xl border border-border bg-surface p-4 text-sm"
    >
      <h3 className="flex items-center gap-2 font-semibold">
        <Dices className="size-4 text-muted" aria-hidden /> Dice log
      </h3>
      {rolls.length === 0 ? (
        <p className="text-muted">No rolls yet.</p>
      ) : (
        <ol className="max-h-72 space-y-1 overflow-auto font-mono text-xs">
          {rolls.map((e, i) => (
            <li key={i} className="text-muted">
              {e.text}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

/** Author tools: jump anywhere, edit state, force the next roll. Recorded like moves. */
function Debug({
  bookId,
  view,
  onInput,
}: {
  bookId: string
  view: PlayOut
  onInput: (i: PlayInput) => void
}) {
  const graph = useBookGraph(bookId)
  const [open, setOpen] = useState(false)
  const [flag, setFlag] = useState('')
  const nodes = useMemo(
    () =>
      [...(graph.data?.nodes ?? [])]
        .sort((a, b) => a.title.localeCompare(b.title))
        .map((n) => ({ value: n.id, label: n.title })),
    [graph.data],
  )
  return (
    <section aria-label="Debug" className="rounded-xl border border-dashed border-border">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-sm font-medium text-muted hover:text-text"
      >
        <Bug className="size-4" aria-hidden /> Debug drawer
      </button>
      {open && (
        <div className="grid gap-4 border-t border-dashed border-border p-4 sm:grid-cols-2">
          <Field label="Jump to node">
            {(id) => (
              <Select
                id={id}
                value={null}
                placeholder="Choose a node…"
                options={nodes}
                onValueChange={(node_id) => node_id && onInput({ kind: 'jump', node_id })}
              />
            )}
          </Field>
          <Field label="Force the next roll" hint="Choices, tests and tables (not combat rounds)">
            {(id) => (
              <NumberInput
                id={id}
                value={null}
                allowEmpty
                placeholder="Total"
                onCommit={(total) => total !== null && onInput({ kind: 'force', total })}
              />
            )}
          </Field>
          <div className="space-y-1 sm:col-span-2">
            <p className="text-xs font-medium text-muted">Stats</p>
            <div className="flex flex-wrap gap-2">
              {view.stats.map((s) => (
                <label key={s.key} className="flex items-center gap-1.5 text-xs">
                  {s.key}
                  <NumberInput
                    aria-label={`Set ${s.label}`}
                    className="w-20"
                    value={s.value}
                    onCommit={(v) =>
                      v !== null && v !== s.value && onInput({ kind: 'set', stats: { [s.key]: v } })
                    }
                  />
                </label>
              ))}
            </div>
          </div>
          <Field label="Codeword" hint="Enter to toggle">
            {(id) => (
              <TextInput
                id={id}
                value={flag}
                placeholder="e.g. MET_WITCH"
                onCommit={(f) => {
                  const key = f.trim()
                  if (!key) return
                  onInput({ kind: 'set', flags: { [key]: !view.flags.includes(key) } })
                  setFlag('')
                }}
              />
            )}
          </Field>
          <ItemSetter view={view} onInput={onInput} />
        </div>
      )}
    </section>
  )
}

function ItemSetter({ view, onInput }: { view: PlayOut; onInput: (i: PlayInput) => void }) {
  const [key, setKey] = useState('')
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-muted">Item count</p>
      <div className="flex gap-2">
        <TextInput
          aria-label="Item key"
          placeholder="item key"
          value={key}
          onCommit={setKey}
          className="flex-1"
        />
        <NumberInput
          aria-label="Item count"
          className="w-20"
          min={0}
          value={view.items.find((i) => i.key === key)?.count ?? 0}
          onCommit={(n) =>
            key.trim() && n !== null && onInput({ kind: 'set', items: { [key.trim()]: n } })
          }
        />
      </div>
    </div>
  )
}
