import { Plus, Trash2 } from 'lucide-react'

import type { Effect } from '@/api/types'
import { GbxField } from '@/components/gbx/GbxField'
import { useVocabulary } from '@/components/gbx/vocabulary'
import { Button } from '@/components/ui/button'
import { Checkbox, NumberInput, Select, TextInput } from '@/components/ui/inputs'

import { type EffectIn, toInput } from './effects'

type Op = EffectIn['op'] & string

const OPS: { value: Op; label: string }[] = [
  { value: 'modify', label: 'Change stat' },
  { value: 'set', label: 'Set stat' },
  { value: 'give', label: 'Give item' },
  { value: 'take', label: 'Take item' },
  { value: 'equip', label: 'Equip item' },
  { value: 'set_flag', label: 'Give codeword' },
  { value: 'clear_flag', label: 'Remove codeword' },
  { value: 'learn', label: 'Learn skill' },
]

function blank(op: Op, prev?: EffectIn): EffectIn {
  const keep = { once: prev?.once, min_tier: prev?.min_tier }
  switch (op) {
    case 'modify':
      return { op, stat: 'STAMINA', amount: '-2', ...keep } as EffectIn
    case 'set':
      return { op, stat: 'STAMINA', value: '0', ...keep } as EffectIn
    case 'give':
    case 'take':
      return { op, item: '', qty: 1, ...keep } as EffectIn
    case 'equip':
      return { op, item: '', ...keep } as EffectIn
    case 'set_flag':
    case 'clear_flag':
      return { op, flag: '', ...keep } as EffectIn
    case 'learn':
      return { op, skill: '', ...keep } as EffectIn
  }
}

/** A plain whole number (the quick money field only edits those). */
const WHOLE = /^-?\d+$/

/**
 * Quick money field: edits the first "change <currency> by a number" effect,
 * adding or removing it, so authors needn't build one by hand.
 */
export function CurrencyQuick({
  effects,
  onChange,
  currency,
  defaultOnce,
}: {
  effects: EffectIn[]
  onChange: (next: EffectIn[]) => void
  currency: { key: string; label: string }
  defaultOnce: boolean
}) {
  const at = effects.findIndex(
    (e) => e.op === 'modify' && (e as { stat?: string }).stat === currency.key,
  )
  const cur = at >= 0 ? (effects[at] as EffectIn & { amount: string; once?: boolean }) : null
  if (cur && !WHOLE.test(cur.amount.trim()))
    return (
      <p className="text-xs text-muted">
        {currency.label}: <code className="font-mono">{cur.amount}</code> (edit it below)
      </p>
    )
  const commit = (n: number | null) => {
    if (!n) {
      if (cur) onChange(effects.filter((_, j) => j !== at))
    } else if (cur) onChange(effects.map((e, j) => (j === at ? { ...cur, amount: String(n) } : e)))
    else
      onChange([
        { op: 'modify', stat: currency.key, amount: String(n), once: defaultOnce } as EffectIn,
        ...effects,
      ])
  }
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="font-medium">{currency.label}</span>
      <NumberInput
        aria-label={`${currency.label} gained or lost`}
        allowEmpty
        placeholder="0"
        value={cur ? Number(cur.amount) : null}
        onCommit={commit}
        className="w-24"
      />
      <span className="text-xs text-muted">gained (negative to pay or lose)</span>
      {cur && (
        <Checkbox
          label="Only the first time"
          checked={!!cur.once}
          onCheckedChange={(once) =>
            onChange(effects.map((e, j) => (j === at ? { ...cur, once } : e)))
          }
        />
      )}
    </div>
  )
}

export function EffectsEditor({
  value,
  onChange,
  tier,
  emptyText = 'No effects.',
  quickCurrency = false,
}: {
  value: Effect[]
  onChange: (next: EffectIn[]) => void
  tier?: string | null
  emptyText?: string
  /** Show a quick field for gaining or paying money (first-time-only by default when true). */
  quickCurrency?: boolean | 'repeat'
}) {
  const vocab = useVocabulary()
  const effects = value.map(toInput)
  const set = (i: number, patch: Partial<EffectIn>) =>
    onChange(effects.map((e, j) => (j === i ? ({ ...e, ...patch } as EffectIn) : e)))
  const remove = (i: number) => onChange(effects.filter((_, j) => j !== i))
  const tierOptions = vocab.tiers.map((t) => ({ value: t.key, label: `${t.label}+` }))

  return (
    <div className="space-y-2">
      {quickCurrency && vocab.currency && (
        <CurrencyQuick
          effects={effects}
          onChange={onChange}
          currency={vocab.currency}
          defaultOnce={quickCurrency === true}
        />
      )}
      {effects.length === 0 && <p className="text-xs text-muted">{emptyText}</p>}
      {effects.map((e, i) => {
        const r = e as Record<string, unknown>
        return (
          <div key={i} className="space-y-2 rounded-md border border-border p-2">
            <div className="flex items-center gap-2">
              <Select
                aria-label="Effect type"
                value={e.op as Op}
                onValueChange={(op) =>
                  op && onChange(effects.map((x, j) => (j === i ? blank(op, x) : x)))
                }
                options={OPS}
                className="w-40"
              />
              {(e.op === 'modify' || e.op === 'set') && (
                <Select
                  aria-label="Stat"
                  value={String(r.stat)}
                  onValueChange={(stat) => stat && set(i, { stat } as Partial<EffectIn>)}
                  options={vocab.stats.map((s) => ({ value: s.key, label: s.label }))}
                  className="flex-1"
                />
              )}
              {(e.op === 'give' || e.op === 'take' || e.op === 'equip') && (
                <Select
                  aria-label="Item"
                  value={String(r.item) || null}
                  placeholder="Choose item…"
                  onValueChange={(item) => set(i, { item: item ?? '' } as Partial<EffectIn>)}
                  options={vocab.items.map((s) => ({ value: s.key, label: s.label }))}
                  className="flex-1"
                />
              )}
              {(e.op === 'give' || e.op === 'take') && (
                <NumberInput
                  aria-label="Quantity"
                  min={1}
                  value={Number(r.qty ?? 1)}
                  onCommit={(qty) => set(i, { qty: Math.max(1, qty ?? 1) } as Partial<EffectIn>)}
                  className="w-16"
                />
              )}
              {(e.op === 'set_flag' || e.op === 'clear_flag') && (
                <>
                  <TextInput
                    aria-label="Codeword"
                    list="gbx-flags"
                    placeholder="CODEWORD"
                    value={String(r.flag ?? '')}
                    onCommit={(flag) =>
                      set(i, {
                        flag: flag
                          .trim()
                          .toUpperCase()
                          .replace(/[^A-Z0-9_]/g, '_'),
                      } as Partial<EffectIn>)
                    }
                    className="flex-1 font-mono uppercase"
                  />
                  <datalist id="gbx-flags">
                    {vocab.flags.map((f) => (
                      <option key={f.key} value={f.key} />
                    ))}
                  </datalist>
                </>
              )}
              {e.op === 'learn' && (
                <Select
                  aria-label="Skill"
                  value={String(r.skill) || null}
                  placeholder="Choose skill…"
                  onValueChange={(skill) => set(i, { skill: skill ?? '' } as Partial<EffectIn>)}
                  options={vocab.skills.map((s) => ({ value: s.key, label: s.label }))}
                  className="flex-1"
                />
              )}
              <Button
                variant="ghost"
                size="icon"
                aria-label="Remove effect"
                onClick={() => remove(i)}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
            {(e.op === 'modify' || e.op === 'set') && (
              <GbxField
                label={e.op === 'modify' ? 'Amount (negative to lose)' : 'New value'}
                context="amount"
                tier={(r.min_tier as string | undefined) ?? tier}
                value={String(e.op === 'modify' ? r.amount : r.value)}
                placeholder={e.op === 'modify' ? '-2 or 1d6' : '0'}
                onCommit={(src) =>
                  set(
                    i,
                    (e.op === 'modify'
                      ? { amount: src ?? '0' }
                      : { value: src ?? '0' }) as Partial<EffectIn>,
                  )
                }
              />
            )}
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <Checkbox
                label="Only the first time"
                checked={
                  r.once === undefined
                    ? ['give', 'equip', 'set_flag', 'learn'].includes(e.op as string)
                    : !!r.once
                }
                onCheckedChange={(once) => set(i, { once } as Partial<EffectIn>)}
              />
              <Select
                aria-label="Minimum tier"
                value={(r.min_tier as string | undefined) ?? null}
                placeholder="All tiers"
                onValueChange={(min_tier) => set(i, { min_tier } as Partial<EffectIn>)}
                options={tierOptions}
                className="w-32 py-1 text-xs"
              />
            </div>
          </div>
        )
      })}
      <Button variant="outline" size="sm" onClick={() => onChange([...effects, blank('modify')])}>
        <Plus className="size-4" /> Add effect
      </Button>
    </div>
  )
}
