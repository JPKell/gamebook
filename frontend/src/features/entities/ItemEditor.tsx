import { Trash2 } from 'lucide-react'

import { useRuleSystems } from '@/api/queries'
import type { components } from '@/api/schema'
import { GbxField } from '@/components/gbx/GbxField'
import { useVocabulary } from '@/components/gbx/vocabulary'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Checkbox, NumberInput, Select, TextArea, TextInput } from '@/components/ui/inputs'
import { EffectsEditor } from '@/features/story/inspector/EffectsEditor'
import { EntityArt } from '@/features/art/EntityArt'

import { type Category, CATEGORIES } from './categories'
import { type ItemUpdate, useDeleteEntity, useSaveEntity, useWhereUsed } from './api'
import { Rows } from './EnemyEditor'
import { Panel } from './EntityHeader'
import { ProblemList } from './ProblemList'
import type { Problem } from './problems'
import { ScopeSelect } from './ScopeSelect'
import { WhereUsed } from './WhereUsed'

type Item = components['schemas']['ItemOut']

export function ItemEditor({
  seriesId,
  item,
  problems,
  onDeleted,
}: {
  seriesId: string
  item: Item
  problems: Problem[] | undefined
  onDeleted: () => void
}) {
  const vocab = useVocabulary()
  const systems = useRuleSystems(seriesId)
  const saveEntity = useSaveEntity('items', seriesId)
  const remove = useDeleteEntity('items', seriesId)
  const used = useWhereUsed(seriesId, 'item', item.key)
  const save = (patch: ItemUpdate | ((cur: Item) => ItemUpdate)) => saveEntity(item.id, patch)

  const slots = [
    ...new Set(
      (systems.data?.find((r) => r.is_active)?.definition.tiers ?? []).flatMap(
        (t) => t.slots ?? [],
      ),
    ),
  ]
  const category = CATEGORIES.find((c) => c.value === item.category)
  const tierOptions = vocab.tiers.map((t) => ({ value: t.key, label: `${t.label} and up` }))
  const statOptions = vocab.stats.map((s) => ({ value: s.key, label: s.label }))

  const del = () => {
    const n = used.data?.refs.length ?? 0
    const msg = n
      ? `${item.name} is used in ${n} place(s). Delete it anyway? Those references will break.`
      : `Delete ${item.name}?`
    if (window.confirm(msg)) remove.mutate({ id: item.id, force: n > 0 }, { onSuccess: onDeleted })
  }

  return (
    <div className="space-y-4 pb-10">
      <div className="flex items-center gap-2">
        <h2 className="text-xl font-semibold">{item.name}</h2>
        <code className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted">{item.key}</code>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto text-danger"
          onClick={del}
          disabled={used.isPending}
        >
          <Trash2 className="size-4" /> Delete
        </Button>
      </div>
      <ProblemList problems={problems} />

      <Panel title="Details">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          <Field label="Name">
            {(id) => (
              <TextInput
                id={id}
                value={item.name}
                onCommit={(name) => name.trim() && save({ name })}
              />
            )}
          </Field>
          <Field label="Key" hint="Used in conditions and effects">
            {(id) => (
              <TextInput id={id} value={item.key} onCommit={(key) => key.trim() && save({ key })} />
            )}
          </Field>
          <Field label="Available in">
            {(id) => (
              <ScopeSelect
                id={id}
                seriesId={seriesId}
                value={item.book_id}
                onChange={(book_id) => save({ book_id })}
              />
            )}
          </Field>
          <Field label="Category" hint={category?.hint}>
            {(id) => (
              <Select
                id={id}
                value={item.category as Category}
                options={CATEGORIES}
                onValueChange={(c) =>
                  c && save(c === 'equipment' ? { category: c } : { category: c, slot: null })
                }
              />
            )}
          </Field>
          {item.category === 'equipment' && (
            <Field
              label="Slot"
              hint={slots.length ? undefined : 'The rules define no equipment slots.'}
            >
              {(id) => (
                <Select
                  id={id}
                  value={item.slot ?? null}
                  placeholder="No slot"
                  options={[
                    ...slots,
                    ...(item.slot && !slots.includes(item.slot) ? [item.slot] : []),
                  ].map((s) => ({ value: s, label: s }))}
                  onValueChange={(slot) => save({ slot })}
                />
              )}
            </Field>
          )}
          <Field label="Value" hint="Shop price in the currency stat">
            {(id) => (
              <NumberInput
                id={id}
                min={0}
                value={item.value}
                onCommit={(value) => value !== null && value >= 0 && save({ value })}
              />
            )}
          </Field>
          {item.category === 'consumable' && (
            <Field label="Uses" hint="Empty: one use per item">
              {(id) => (
                <NumberInput
                  id={id}
                  min={1}
                  allowEmpty
                  value={item.uses ?? null}
                  onCommit={(uses) => (uses === null || uses >= 1) && save({ uses })}
                />
              )}
            </Field>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <Checkbox
            label="Stackable"
            checked={item.stackable}
            onCheckedChange={(stackable) => save({ stackable })}
          />
          {item.stackable && (
            <Field label="Max per stack" inline>
              {(id) => (
                <NumberInput
                  id={id}
                  className="w-24"
                  min={1}
                  allowEmpty
                  placeholder="No limit"
                  value={item.max_stack ?? null}
                  onCommit={(max_stack) =>
                    (max_stack === null || max_stack >= 1) && save({ max_stack })
                  }
                />
              )}
            </Field>
          )}
        </div>
        <Field label="Description">
          {(id) => (
            <TextArea
              id={id}
              rows={2}
              value={item.description}
              onCommit={(description) => save({ description })}
            />
          )}
        </Field>
      </Panel>

      <Panel title="Stat modifiers">
        <p className="text-xs text-muted">
          Added to the reader's stat (SKILL, ARMOR, …) while the item is in effect, in tests,
          conditions and combat alike.{' '}
          {item.slot
            ? `It must be equipped in the ${item.slot} slot to count.`
            : 'Any item without a slot counts while carried.'}{' '}
          Limit a modifier to higher tiers to keep Basic simple.
        </p>
        <Rows
          rows={item.modifiers}
          empty="No modifiers."
          addLabel="Add modifier"
          disabled={!statOptions.length}
          blank={{ stat: statOptions[0]?.value ?? '', amount: '1', min_tier: null }}
          onChange={(f) => save((cur) => ({ modifiers: f(cur.modifiers) }))}
          render={(mod, set) => (
            <>
              <Select
                aria-label="Modifier stat"
                className="w-40"
                value={mod.stat}
                options={
                  statOptions.some((o) => o.value === mod.stat)
                    ? statOptions
                    : [...statOptions, { value: mod.stat, label: `${mod.stat} (missing)` }]
                }
                onValueChange={(stat) => stat && set({ stat })}
              />
              <div className="w-40">
                <GbxField
                  label="Modifier amount"
                  context="amount"
                  tier={mod.min_tier}
                  value={mod.amount}
                  onCommit={(amount) => amount && set({ amount })}
                />
              </div>
              <Select
                aria-label="Modifier tier"
                className="w-44"
                value={mod.min_tier ?? null}
                placeholder="Every tier"
                options={tierOptions}
                onValueChange={(min_tier) => set({ min_tier })}
              />
            </>
          )}
        />
      </Panel>

      {(item.category === 'consumable' || item.use_effects.length > 0) && (
        <Panel title="When used">
          <EffectsEditor
            value={item.use_effects}
            onChange={(use_effects) => save({ use_effects })}
            emptyText="Using it does nothing yet."
          />
        </Panel>
      )}

      <Panel title="Placements">
        <WhereUsed seriesId={seriesId} targetType="item" entityKey={item.key} showTotal />
      </Panel>
      <EntityArt seriesId={seriesId} targetType="item" targetId={item.id} name={item.name} />
    </div>
  )
}
