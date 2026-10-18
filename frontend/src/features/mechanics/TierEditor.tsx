import { ChevronDown, ChevronRight, Plus, RotateCcw, Trash2, X } from 'lucide-react'
import { createContext, type ReactNode, useContext, useState } from 'react'
import { toast } from 'sonner'

import type { components } from '@/api/schema'
import { GbxField } from '@/components/gbx/GbxField'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Checkbox, NumberInput, Select, TextArea, TextInput } from '@/components/ui/inputs'
import { EffectsEditor } from '@/features/story/inspector/EffectsEditor'
import { cn } from '@/lib/utils'

import {
  type ClassDef,
  type CombatDef,
  type DefList,
  findTier,
  remove,
  removeTier,
  type RuleSystemDef,
  setCombat,
  type SkillDef,
  slugKey,
  type StatDef,
  type TestDef,
  type TierDef,
  updateTier,
  upsert,
} from './defs'

type TierView = components['schemas']['TierView']

interface Props {
  def: RuleSystemDef
  tierKey: string
  view: TierView
  save: (next: RuleSystemDef) => void
  onDeleted: () => void
}

/** Edit one tier: own definitions are editable; inherited ones can be overridden. */
export function TierEditor({ def, tierKey, view, save, onDeleted }: Props) {
  const tier = findTier(def, tierKey)
  if (!tier) return null
  const labelOf = (key: string) => def.tiers.find((t) => t.key === key)?.label ?? key
  const edit = (fn: (t: TierDef) => void) => save(updateTier(def, tierKey, fn))
  const own = <L extends DefList>(list: L) =>
    new Set(((tier[list] ?? []) as { key: string }[]).map((d) => d.key))
  const strip = <T extends object>(row: T) => {
    const {
      introduced: _i,
      origin: _o,
      ...rest
    } = row as T & { introduced?: string; origin?: string }
    return rest
  }

  return (
    <div className="space-y-4">
      <Section title="Tier" defaultOpen>
        <TierMeta def={def} tier={tier} save={save} edit={edit} onDeleted={onDeleted} />
      </Section>

      <Section title="Stats & resources" count={view.stats.length} defaultOpen>
        <KeyedList
          rows={view.stats}
          own={own('stats')}
          tierKey={tierKey}
          labelOf={labelOf}
          summary={(s) => `${s.applies_to?.join(' & ') ?? 'player'} · starts ${s.initial ?? '0'}`}
          onOverride={(s) => edit((t) => upsert(t, 'stats', strip(s) as StatDef))}
          onRemove={(key) => edit((t) => remove(t, 'stats', key))}
          render={(s) => (
            <StatEditor
              stat={tier.stats!.find((x) => x.key === s.key)!}
              tierKey={tierKey}
              onChange={(next, prev) => edit((t) => upsert(t, 'stats', next, prev))}
            />
          )}
          addLabel="Add stat"
          onAdd={(label) =>
            edit((t) =>
              upsert(t, 'stats', {
                key: slugKey(label, new Set(view.stats.map((s) => s.key)), true),
                label,
                applies_to: ['player'],
                initial: '0',
              }),
            )
          }
        />
      </Section>

      <Section title="Tests" count={view.tests.length}>
        <KeyedList
          rows={view.tests}
          own={own('tests')}
          tierKey={tierKey}
          labelOf={labelOf}
          summary={(t) => `roll ${t.roll ?? '2d6'} · succeed if ${t.success}`}
          onOverride={(t) => edit((x) => upsert(x, 'tests', strip(t) as TestDef))}
          onRemove={(key) => edit((t) => remove(t, 'tests', key))}
          render={(t) => (
            <TestEditor
              test={tier.tests!.find((x) => x.key === t.key)!}
              tierKey={tierKey}
              onChange={(next, prev) => edit((x) => upsert(x, 'tests', next, prev))}
            />
          )}
          addLabel="Add test"
          onAdd={(label) =>
            edit((t) =>
              upsert(t, 'tests', {
                key: slugKey(label, new Set(view.tests.map((s) => s.key))),
                label,
                roll: '2d6',
                success: 'roll <= player.SKILL',
              }),
            )
          }
        />
      </Section>

      <Section title="Skills" count={view.skills.length}>
        <KeyedList
          rows={view.skills}
          own={own('skills')}
          tierKey={tierKey}
          labelOf={labelOf}
          summary={(s) => s.description || ''}
          onOverride={(s) => edit((t) => upsert(t, 'skills', strip(s) as SkillDef))}
          onRemove={(key) => edit((t) => remove(t, 'skills', key))}
          render={(s) => (
            <SimpleDefEditor
              item={tier.skills!.find((x) => x.key === s.key)!}
              onChange={(next, prev) => edit((t) => upsert(t, 'skills', next, prev))}
            />
          )}
          addLabel="Add skill"
          onAdd={(label) =>
            edit((t) =>
              upsert(t, 'skills', {
                key: slugKey(label, new Set(view.skills.map((s) => s.key)), true),
                label,
              }),
            )
          }
        />
      </Section>

      <Section title="Classes" count={view.classes.length}>
        <KeyedList
          rows={view.classes}
          own={own('classes')}
          tierKey={tierKey}
          labelOf={labelOf}
          summary={(c) => (c.skills?.length ? `skills: ${c.skills.join(', ')}` : 'no skills')}
          onOverride={(c) => edit((t) => upsert(t, 'classes', strip(c) as ClassDef))}
          onRemove={(key) => edit((t) => remove(t, 'classes', key))}
          render={(c) => {
            const cls = tier.classes!.find((x) => x.key === c.key)!
            return (
              <div className="space-y-3">
                <SimpleDefEditor
                  item={cls}
                  onChange={(next, prev) =>
                    edit((t) => upsert(t, 'classes', { ...cls, ...next }, prev))
                  }
                />
                <fieldset>
                  <legend className="mb-1 text-xs font-medium text-muted">Starting skills</legend>
                  <div className="flex flex-wrap gap-3">
                    {view.skills.map((s) => (
                      <Checkbox
                        key={s.key}
                        label={s.label}
                        checked={!!cls.skills?.includes(s.key)}
                        onCheckedChange={(on) =>
                          edit((t) =>
                            upsert(t, 'classes', {
                              ...cls,
                              skills: on
                                ? [...(cls.skills ?? []), s.key]
                                : (cls.skills ?? []).filter((k) => k !== s.key),
                            }),
                          )
                        }
                      />
                    ))}
                    {view.skills.length === 0 && (
                      <span className="text-xs text-muted">Define skills first.</span>
                    )}
                  </div>
                </fieldset>
              </div>
            )
          }}
          addLabel="Add class"
          onAdd={(label) =>
            edit((t) =>
              upsert(t, 'classes', {
                key: slugKey(label, new Set(view.classes.map((s) => s.key))),
                label,
                skills: [],
              }),
            )
          }
        />
      </Section>

      <Section title="Equipment slots" count={view.slots.length}>
        <Slots view={view} tier={tier} tierKey={tierKey} labelOf={labelOf} edit={edit} />
      </Section>

      <Section title="Combat" defaultOpen>
        <CombatEditor view={view} tier={tier} tierKey={tierKey} labelOf={labelOf} edit={edit} />
      </Section>

      <Section title="Rules chapter text">
        <p className="mb-2 text-xs text-muted">
          Shown to readers at this tier in print and in the player (markdown).
        </p>
        <TextArea
          aria-label="Rules chapter text"
          value={tier.rules_text ?? ''}
          onCommit={(rules_text) => edit((t) => void (t.rules_text = rules_text))}
          className="min-h-40"
        />
      </Section>
    </div>
  )
}

// ── keys ──────────────────────────────────────────────────────────────────

/** Per-row key rules: keys already used in this list, and whether the key is
 * fixed (an override must keep the inherited key, or it stops overriding). */
const KeyRules = createContext<{ taken: Set<string>; locked: boolean }>({
  taken: new Set(),
  locked: false,
})

function KeyInput({
  id,
  value,
  onRename,
}: {
  id: string
  value: string
  onRename: (key: string) => void
}) {
  const { taken, locked } = useContext(KeyRules)
  return (
    <TextInput
      id={id}
      value={value}
      disabled={locked}
      title={
        locked
          ? 'Overrides keep the inherited key'
          : 'Used in formulas; content using the old key is not updated'
      }
      className="font-mono"
      onCommit={(key) => {
        if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(key))
          toast.error('Keys start with a letter and use letters, digits and _')
        else if (taken.has(key)) toast.error(`${key} is already used here`)
        else onRename(key)
      }}
    />
  )
}

// ── layout pieces ──────────────────────────────────────────────────────────

function Section({
  title,
  count,
  defaultOpen = false,
  children,
}: {
  title: string
  count?: number
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className="rounded-xl border border-border bg-surface" aria-label={title}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-4 py-3 text-left font-semibold"
      >
        {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        {title}
        {count !== undefined && (
          <span className="rounded-full bg-surface-2 px-2 text-xs font-normal text-muted">
            {count}
          </span>
        )}
      </button>
      {open && <div className="border-t border-border p-4">{children}</div>}
    </section>
  )
}

function Origin({ label, kind }: { label: string; kind: 'from' | 'overrides' }) {
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 text-[11px]',
        kind === 'from' ? 'bg-surface-2 text-muted' : 'bg-accent/12 text-accent',
      )}
    >
      {kind === 'from' ? `from ${label}` : `overrides ${label}`}
    </span>
  )
}

interface Row {
  key: string
  label: string
  introduced: string
  origin: string
}

function KeyedList<R extends Row>({
  rows,
  own,
  tierKey,
  labelOf,
  summary,
  onOverride,
  onRemove,
  render,
  addLabel,
  onAdd,
}: {
  rows: R[]
  own: Set<string>
  tierKey: string
  labelOf: (key: string) => string
  summary: (row: R) => string
  onOverride: (row: R) => void
  onRemove: (key: string) => void
  render: (row: R) => ReactNode
  addLabel: string
  onAdd: (label: string) => void
}) {
  const [expanded, setExpanded] = useState<string | null>(null)
  return (
    <div className="space-y-2">
      {rows.length === 0 && <p className="text-sm text-muted">None yet.</p>}
      {rows.map((row) => {
        const isOwn = own.has(row.key)
        const inheritedFrom = row.introduced !== tierKey ? row.introduced : null
        const open = isOwn && expanded === row.key
        return (
          <div
            key={row.key}
            className={cn(
              'rounded-lg border',
              isOwn ? 'border-border' : 'border-dashed border-border bg-surface-2/40',
            )}
          >
            <div className="flex items-center gap-2 px-3 py-2">
              <button
                type="button"
                disabled={!isOwn}
                onClick={() => setExpanded(open ? null : row.key)}
                aria-expanded={isOwn ? open : undefined}
                className="flex min-w-0 flex-1 items-center gap-2 text-left disabled:cursor-default"
              >
                {isOwn &&
                  (open ? (
                    <ChevronDown className="size-4 shrink-0" />
                  ) : (
                    <ChevronRight className="size-4 shrink-0" />
                  ))}
                <span className={cn('font-mono text-xs', !isOwn && 'text-muted')}>{row.key}</span>
                <span className={cn('truncate text-sm font-medium', !isOwn && 'text-muted')}>
                  {row.label}
                </span>
                <span className="truncate text-xs text-muted">{summary(row)}</span>
              </button>
              {inheritedFrom && (
                <Origin label={labelOf(inheritedFrom)} kind={isOwn ? 'overrides' : 'from'} />
              )}
              {!isOwn ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    onOverride(row)
                    setExpanded(row.key)
                  }}
                >
                  Override
                </Button>
              ) : inheritedFrom ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onRemove(row.key)}
                  title={`Use the ${labelOf(inheritedFrom)} definition again`}
                >
                  <RotateCcw className="size-3.5" /> Revert
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Delete ${row.label}`}
                  onClick={() => onRemove(row.key)}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              )}
            </div>
            {open && (
              <KeyRules.Provider
                value={{
                  taken: new Set(rows.map((r) => r.key).filter((k) => k !== row.key)),
                  locked: row.introduced !== tierKey,
                }}
              >
                <div className="border-t border-border px-3 py-3">{render(row)}</div>
              </KeyRules.Provider>
            )}
          </div>
        )
      })}
      <AddRow label={addLabel} onAdd={onAdd} />
    </div>
  )
}

function AddRow({ label, onAdd }: { label: string; onAdd: (name: string) => void }) {
  const [name, setName] = useState('')
  return (
    <form
      className="flex gap-2 pt-1"
      onSubmit={(e) => {
        e.preventDefault()
        if (name.trim()) {
          onAdd(name.trim())
          setName('')
        }
      }}
    >
      <input
        aria-label={`${label}: name`}
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={`${label}…`}
        className="h-8 min-w-0 flex-1 rounded-md border border-border bg-bg px-2.5 text-sm focus:border-accent focus:outline-none"
      />
      <Button type="submit" variant="outline" size="sm" disabled={!name.trim()}>
        <Plus className="size-4" /> {label}
      </Button>
    </form>
  )
}

// ── editors ───────────────────────────────────────────────────────────────

function TierMeta({
  def,
  tier,
  save,
  edit,
  onDeleted,
}: {
  def: RuleSystemDef
  tier: TierDef
  save: (next: RuleSystemDef) => void
  edit: (fn: (t: TierDef) => void) => void
  onDeleted: () => void
}) {
  const index = def.tiers.findIndex((t) => t.key === tier.key)
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Name">
          {(id) => (
            <TextInput
              id={id}
              value={tier.label}
              onCommit={(label) => label.trim() && edit((t) => void (t.label = label.trim()))}
            />
          )}
        </Field>
        <Field label="Inherits from" hint="Inherited rules can be overridden here.">
          {(id) => (
            <Select
              id={id}
              value={tier.parent ?? null}
              placeholder="Nothing (base tier)"
              onValueChange={(parent) => edit((t) => void (t.parent = parent))}
              options={def.tiers.slice(0, index).map((t) => ({ value: t.key, label: t.label }))}
            />
          )}
        </Field>
      </div>
      <Field label="Description">
        {(id) => (
          <TextArea
            id={id}
            value={tier.description ?? ''}
            onCommit={(description) => edit((t) => void (t.description = description))}
            className="min-h-12"
          />
        )}
      </Field>
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-muted">key: {tier.key}</span>
        <Button
          variant="ghost"
          size="sm"
          className="text-danger"
          onClick={() => {
            try {
              const next = removeTier(def, tier.key)
              if (
                window.confirm(
                  `Delete the ${tier.label} tier? Content using it as a minimum tier will show problems.`,
                )
              ) {
                save(next)
                onDeleted()
              }
            } catch (e) {
              window.alert((e as Error).message)
            }
          }}
        >
          <Trash2 className="size-4" /> Delete tier
        </Button>
      </div>
    </div>
  )
}

function StatEditor({
  stat,
  tierKey,
  onChange,
}: {
  stat: StatDef
  tierKey: string
  onChange: (next: StatDef, prevKey: string) => void
}) {
  const set = (patch: Partial<StatDef>) => onChange({ ...stat, ...patch }, stat.key)
  const applies = new Set(stat.applies_to ?? ['player'])
  const toggle = (who: 'player' | 'enemy', on: boolean) => {
    const next = new Set(applies)
    if (on) next.add(who)
    else next.delete(who)
    set({ applies_to: (['player', 'enemy'] as const).filter((w) => next.has(w)) })
  }
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        <Field label="Label">
          {(id) => <TextInput id={id} value={stat.label} onCommit={(label) => set({ label })} />}
        </Field>
        <Field label="Key" hint="Used in formulas">
          {(id) => <KeyInput id={id} value={stat.key} onRename={(key) => set({ key })} />}
        </Field>
        <Field label="Kind">
          {(id) => (
            <Select
              id={id}
              value={stat.kind ?? 'stat'}
              onValueChange={(kind) => kind && set({ kind })}
              options={[
                { value: 'stat', label: 'Stat' },
                { value: 'resource', label: 'Resource (money)' },
              ]}
            />
          )}
        </Field>
      </div>
      <div className="flex gap-4">
        <Checkbox
          label="Player has it"
          checked={applies.has('player')}
          onCheckedChange={(on) => toggle('player', on)}
        />
        <Checkbox
          label="Enemies have it"
          checked={applies.has('enemy')}
          onCheckedChange={(on) => toggle('enemy', on)}
        />
      </div>
      <Field label="Starting value (rolled at character creation)">
        {() => (
          <GbxField
            label="Starting value"
            context="stat_initial"
            tier={tierKey}
            value={stat.initial ?? '0'}
            onCommit={(initial) => set({ initial: initial ?? '0' })}
          />
        )}
      </Field>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Minimum">
          {(id) => (
            <NumberInput
              id={id}
              allowEmpty
              value={stat.min ?? null}
              onCommit={(min) => set({ min })}
            />
          )}
        </Field>
        <Field label="Maximum">
          {(id) => (
            <NumberInput
              id={id}
              allowEmpty
              value={stat.max ?? null}
              onCommit={(max) => set({ max })}
            />
          )}
        </Field>
        <Field label="Defeated at">
          {(id) => (
            <NumberInput
              id={id}
              allowEmpty
              value={stat.defeat_at ?? null}
              onCommit={(defeat_at) => set({ defeat_at })}
            />
          )}
        </Field>
        <div className="flex items-end pb-1.5">
          <Checkbox
            label="Can't exceed start"
            checked={!!stat.max_is_initial}
            onCheckedChange={(max_is_initial) => set({ max_is_initial })}
          />
        </div>
      </div>
    </div>
  )
}

function TestEditor({
  test,
  tierKey,
  onChange,
}: {
  test: TestDef
  tierKey: string
  onChange: (next: TestDef, prevKey: string) => void
}) {
  const set = (patch: Partial<TestDef>) => onChange({ ...test, ...patch }, test.key)
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Label">
          {(id) => <TextInput id={id} value={test.label} onCommit={(label) => set({ label })} />}
        </Field>
        <Field label="Key">
          {(id) => <KeyInput id={id} value={test.key} onRename={(key) => set({ key })} />}
        </Field>
      </div>
      <Field label="Roll">
        {() => (
          <GbxField
            label="Roll"
            context="test_roll"
            tier={tierKey}
            value={test.roll ?? '2d6'}
            onCommit={(roll) => set({ roll: roll ?? '2d6' })}
          />
        )}
      </Field>
      <Field label="Succeeds when">
        {() => (
          <GbxField
            label="Succeeds when"
            context="test_success"
            tier={tierKey}
            value={test.success}
            placeholder="roll <= player.LUCK"
            onCommit={(success) => success && set({ success })}
          />
        )}
      </Field>
      <Field label="Afterwards">
        {() => (
          <EffectsEditor
            value={(test.after ?? []) as never}
            tier={tierKey}
            onChange={(after) => set({ after: after as TestDef['after'] })}
            emptyText="Nothing changes after the test."
          />
        )}
      </Field>
    </div>
  )
}

function SimpleDefEditor<T extends SkillDef | ClassDef>({
  item,
  onChange,
}: {
  item: T
  onChange: (next: T, prevKey: string) => void
}) {
  const set = (patch: Partial<T>) => onChange({ ...item, ...patch }, item.key)
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Label">
          {(id) => (
            <TextInput
              id={id}
              value={item.label}
              onCommit={(label) => set({ label } as Partial<T>)}
            />
          )}
        </Field>
        <Field label="Key">
          {(id) => (
            <KeyInput id={id} value={item.key} onRename={(key) => set({ key } as Partial<T>)} />
          )}
        </Field>
      </div>
      <Field label="Description">
        {(id) => (
          <TextArea
            id={id}
            value={item.description ?? ''}
            onCommit={(description) => set({ description } as Partial<T>)}
            className="min-h-12"
          />
        )}
      </Field>
    </div>
  )
}

function Slots({
  view,
  tier,
  tierKey,
  labelOf,
  edit,
}: {
  view: TierView
  tier: TierDef
  tierKey: string
  labelOf: (k: string) => string
  edit: (fn: (t: TierDef) => void) => void
}) {
  return (
    <div className="space-y-3">
      <ul className="flex flex-wrap gap-2">
        {view.slots.map((s) => (
          <li
            key={s.slot}
            className={cn(
              'flex items-center gap-1 rounded-full border px-2.5 py-1 text-sm',
              s.origin === tierKey ? 'border-border' : 'border-dashed border-border text-muted',
            )}
          >
            {s.slot}
            {s.origin !== tierKey ? (
              <span className="text-[11px]">· {labelOf(s.origin)}</span>
            ) : (
              <button
                type="button"
                aria-label={`Remove ${s.slot}`}
                onClick={() =>
                  edit((t) => void (t.slots = (t.slots ?? []).filter((x) => x !== s.slot)))
                }
              >
                <X className="size-3.5" />
              </button>
            )}
          </li>
        ))}
        {view.slots.length === 0 && (
          <li className="text-sm text-muted">No slots: equipment modifiers apply while carried.</li>
        )}
      </ul>
      <AddRow
        label="Add slot"
        onAdd={(name) => {
          const slot = name.toLowerCase().replace(/[^a-z0-9]+/g, '_')
          if (!view.slots.some((s) => s.slot === slot))
            edit((t) => void (t.slots = [...(tier.slots ?? []), slot]))
        }}
      />
    </div>
  )
}

const COMBAT_FIELDS: {
  field: 'player_attack' | 'enemy_attack' | 'damage'
  label: string
  hint: string
}[] = [
  { field: 'player_attack', label: 'Player attack strength', hint: 'e.g. 2d6 + player.SKILL' },
  { field: 'enemy_attack', label: 'Enemy attack strength', hint: 'e.g. 2d6 + enemy.SKILL' },
  { field: 'damage', label: 'Base damage', hint: 'Before damage rules' },
]

function CombatEditor({
  view,
  tier,
  tierKey,
  labelOf,
  edit,
}: {
  view: TierView
  tier: TierDef
  tierKey: string
  labelOf: (k: string) => string
  edit: (fn: (t: TierDef) => void) => void
}) {
  const own = (tier.combat ?? {}) as CombatDef
  const merged = view.combat
  const origin = (f: string) => view.combat_origin[f]
  const inherited = (f: keyof CombatDef) => own[f] === undefined || own[f] === null
  const set = <K extends keyof CombatDef>(f: K, v: CombatDef[K] | null) =>
    edit((t) => setCombat(t, f, v))
  const shared = view.stats.filter(
    (s) => (s.applies_to ?? []).includes('player') && (s.applies_to ?? []).includes('enemy'),
  )
  const ownHooks = own.damage_hooks ?? []

  // A render helper (not a component) so it isn't re-created as a new type each render.
  const badge = (f: keyof CombatDef) =>
    inherited(f) ? (
      origin(f) ? (
        <Origin label={labelOf(origin(f)!)} kind="from" />
      ) : (
        <span className="text-[11px] text-muted">not set</span>
      )
    ) : (
      <button
        type="button"
        className="text-[11px] text-accent hover:underline"
        onClick={() => set(f, null)}
        title="Clear to inherit"
      >
        set here · inherit instead
      </button>
    )

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted">
        Each round both sides roll attack strength; the higher deals damage to the other’s{' '}
        <strong>{merged.damage_stat ?? '—'}</strong>, passed through the damage rules in order.
        Fields left unset inherit.
      </p>
      {COMBAT_FIELDS.map(({ field, label, hint }) => (
        <div key={field} className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted">{label}</span>
            {badge(field)}
          </div>
          <GbxField
            label={label}
            context="combat_attack"
            tier={tierKey}
            value={(own[field] as string | null | undefined) ?? null}
            placeholder={(merged[field] as string | null | undefined) ?? hint}
            emptyHint={merged[field] ? `Inherited: ${merged[field]}` : hint}
            onCommit={(v) => set(field, v)}
          />
        </div>
      ))}
      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted">Damages</span>
            {badge('damage_stat')}
          </div>
          <Select
            aria-label="Damaged stat"
            value={own.damage_stat ?? null}
            placeholder={merged.damage_stat ? `Inherit (${merged.damage_stat})` : 'Choose…'}
            onValueChange={(v) => set('damage_stat', v)}
            options={shared.map((s) => ({ value: s.key, label: s.label }))}
          />
        </div>
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted">Several enemies</span>
            {badge('multi_enemy')}
          </div>
          <Select
            aria-label="Several enemies"
            value={own.multi_enemy ?? null}
            placeholder={
              merged.multi_enemy
                ? `Inherit (${merged.multi_enemy === 'simultaneous' ? 'all at once' : 'one at a time'})`
                : 'Choose…'
            }
            onValueChange={(v) => set('multi_enemy', v)}
            options={[
              { value: 'sequential', label: 'One at a time' },
              { value: 'simultaneous', label: 'All at once' },
            ]}
          />
        </div>
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted">Fleeing</span>
            {badge('flee_allowed')}
          </div>
          <Select
            aria-label="Fleeing"
            value={
              own.flee_allowed === undefined || own.flee_allowed === null
                ? null
                : own.flee_allowed
                  ? 'yes'
                  : 'no'
            }
            placeholder={
              merged.flee_allowed === false ? 'Inherit (not allowed)' : 'Inherit (allowed)'
            }
            onValueChange={(v) => set('flee_allowed', v === null ? null : v === 'yes')}
            options={[
              { value: 'yes', label: 'Allowed' },
              { value: 'no', label: 'Not allowed' },
            ]}
          />
        </div>
      </div>
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted">Cost of fleeing</span>
          {badge('flee_cost')}
        </div>
        <EffectsEditor
          value={(own.flee_cost ?? merged.flee_cost ?? []) as never}
          tier={tierKey}
          onChange={(cost) => set('flee_cost', cost as CombatDef['flee_cost'])}
          emptyText="Fleeing is free."
        />
      </div>
      <div className="space-y-2">
        <span className="text-xs font-medium text-muted">
          Damage rules (applied in order; use damage, natural, attacker, target)
        </span>
        <ol className="space-y-2">
          {view.damage_hooks
            .filter((h) => h.origin !== tierKey)
            .map((h, i) => (
              <li
                key={`inh-${i}`}
                className="flex items-center gap-2 rounded-md border border-dashed border-border px-2.5 py-1.5 text-sm text-muted"
              >
                <code className="min-w-0 flex-1 truncate font-mono text-xs">{h.expr}</code>
                <Origin label={labelOf(h.origin)} kind="from" />
              </li>
            ))}
          {ownHooks.map((h, i) => (
            <li key={`own-${i}:${h}`} className="flex items-start gap-2">
              <GbxField
                className="min-w-0 flex-1"
                label={`Damage rule ${i + 1}`}
                context="combat_damage"
                tier={tierKey}
                value={h}
                onCommit={(v) =>
                  set(
                    'damage_hooks',
                    v
                      ? ownHooks.map((x, j) => (j === i ? v : x))
                      : ownHooks.filter((_, j) => j !== i),
                  )
                }
              />
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Remove damage rule ${i + 1}`}
                onClick={() =>
                  set(
                    'damage_hooks',
                    ownHooks.filter((_, j) => j !== i),
                  )
                }
              >
                <Trash2 className="size-3.5" />
              </Button>
            </li>
          ))}
        </ol>
        <Button
          variant="outline"
          size="sm"
          onClick={() => set('damage_hooks', [...ownHooks, 'damage'])}
        >
          <Plus className="size-4" /> Add damage rule
        </Button>
      </div>
    </div>
  )
}
