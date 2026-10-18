import { Trash2 } from 'lucide-react'

import { useEntities } from '@/api/queries'
import type { components } from '@/api/schema'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Select, TextArea, TextInput } from '@/components/ui/inputs'
import { useDeleteEntity, useSaveEntity, useWhereUsed } from '@/features/entities/api'
import { Rows } from '@/features/entities/EnemyEditor'
import { Panel } from '@/features/entities/EntityHeader'
import { ScopeSelect } from '@/features/entities/ScopeSelect'
import { WhereUsed } from '@/features/entities/WhereUsed'

import { MentionText } from './MentionText'
import { LORE_TYPES, type LoreType } from './types'

type S = components['schemas']
type Character = S['CharacterOut']
type Lore = S['LoreOut']

const MENTION_HINT =
  'Link people and places with [[key]], e.g. [[mara]] or [[crypt|the old crypt]].'

/** A text area whose [[mentions]] are previewed as links underneath. */
function ProseField({
  label,
  value,
  onCommit,
  seriesId,
  rows = 3,
  always = false,
}: {
  label: string
  value: string
  onCommit: (v: string) => void
  seriesId: string
  rows?: number
  always?: boolean
}) {
  return (
    <Field label={label}>
      {(id) => (
        <div className="space-y-1.5">
          <TextArea id={id} rows={rows} value={value} onCommit={onCommit} />
          {(always || value.includes('[[')) && value.trim() && (
            <MentionText
              text={value}
              seriesId={seriesId}
              className="rounded-md bg-surface-2 px-3 py-2 text-sm"
            />
          )}
        </div>
      )}
    </Field>
  )
}

function Header({
  name,
  entityKey,
  onDelete,
  disabled,
}: {
  name: string
  entityKey: string
  onDelete: () => void
  disabled: boolean
}) {
  return (
    <div className="flex items-center gap-2">
      <h2 className="text-xl font-semibold">{name}</h2>
      <code className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted">{entityKey}</code>
      <Button
        variant="ghost"
        size="sm"
        className="ml-auto text-danger"
        onClick={onDelete}
        disabled={disabled}
      >
        <Trash2 className="size-4" /> Delete
      </Button>
    </div>
  )
}

function useDelete(
  plural: 'characters' | 'lore',
  seriesId: string,
  targetType: string,
  entity: { id: string; key: string; name: string },
  onDeleted: () => void,
) {
  const remove = useDeleteEntity(plural, seriesId)
  const used = useWhereUsed(seriesId, targetType, entity.key)
  const del = () => {
    // An entry mentioning itself doesn't count as being used elsewhere.
    const n = used.data?.refs.filter((r) => r.source_id !== entity.id).length ?? 0
    const msg = n
      ? `${entity.name} is linked or mentioned in ${n} place(s). Delete anyway? Mentions will show as broken links.`
      : `Delete ${entity.name}?`
    if (window.confirm(msg))
      remove.mutate({ id: entity.id, force: n > 0 }, { onSuccess: onDeleted })
  }
  return { del, pending: used.isPending }
}

export function CharacterEditor({
  seriesId,
  character: c,
  onDeleted,
}: {
  seriesId: string
  character: Character
  onDeleted: () => void
}) {
  const saveEntity = useSaveEntity('characters', seriesId)
  const save = (patch: S['CharacterUpdate'] | ((cur: Character) => S['CharacterUpdate'])) =>
    saveEntity(c.id, patch)
  const others = (useEntities('characters', seriesId).data ?? []).filter((x) => x.id !== c.id)
  const { del, pending } = useDelete('characters', seriesId, 'character', c, onDeleted)
  const options = others.map((o) => ({ value: o.key, label: o.name }))

  return (
    <div className="space-y-4 pb-10">
      <Header name={c.name} entityKey={c.key} onDelete={del} disabled={pending} />
      <Panel title="Character">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Field label="Name">
            {(id) => (
              <TextInput
                id={id}
                value={c.name}
                onCommit={(name) => name.trim() && save({ name })}
              />
            )}
          </Field>
          <Field label="Key" hint="For [[mentions]]">
            {(id) => (
              <TextInput id={id} value={c.key} onCommit={(key) => key.trim() && save({ key })} />
            )}
          </Field>
          <Field label="Role">
            {(id) => (
              <TextInput
                id={id}
                value={c.role}
                placeholder="e.g. Rival, mentor"
                onCommit={(role) => save({ role })}
              />
            )}
          </Field>
          <Field label="Appears in">
            {(id) => (
              <ScopeSelect
                id={id}
                seriesId={seriesId}
                value={c.book_id}
                onChange={(book_id) => save({ book_id })}
              />
            )}
          </Field>
        </div>
        <p className="text-xs text-muted">{MENTION_HINT}</p>
        <div className="grid gap-3 lg:grid-cols-2">
          <ProseField
            label="Appearance"
            value={c.appearance}
            seriesId={seriesId}
            onCommit={(appearance) => save({ appearance })}
          />
          <ProseField
            label="Voice & speech"
            value={c.voice}
            seriesId={seriesId}
            onCommit={(voice) => save({ voice })}
          />
          <ProseField
            label="Motivations"
            value={c.motivations}
            seriesId={seriesId}
            onCommit={(motivations) => save({ motivations })}
          />
          <ProseField
            label="Secrets"
            value={c.secrets}
            seriesId={seriesId}
            onCommit={(secrets) => save({ secrets })}
          />
        </div>
        <ProseField
          label="Notes"
          value={c.notes}
          seriesId={seriesId}
          rows={4}
          onCommit={(notes) => save({ notes })}
        />
      </Panel>
      <Panel title="Relationships">
        <Rows
          rows={c.relationships}
          empty="No relationships yet."
          addLabel="Add relationship"
          disabled={!options.length}
          blank={{ character: options[0]?.value ?? '', kind: '', notes: '' }}
          onChange={(f) => save((cur) => ({ relationships: f(cur.relationships) }))}
          render={(r, set) => (
            <>
              <Select
                aria-label="Related character"
                className="w-44"
                value={r.character}
                options={
                  options.some((o) => o.value === r.character)
                    ? options
                    : [...options, { value: r.character, label: `${r.character} (missing)` }]
                }
                onValueChange={(character) => character && set({ character })}
              />
              <TextInput
                aria-label="Relationship"
                className="w-36"
                placeholder="e.g. sister"
                value={r.kind ?? ''}
                onCommit={(kind) => set({ kind })}
              />
              <TextInput
                aria-label="Relationship notes"
                className="flex-1"
                placeholder="Notes"
                value={r.notes ?? ''}
                onCommit={(notes) => set({ notes })}
              />
            </>
          )}
        />
      </Panel>
      <Panel title="Appearances">
        <WhereUsed
          seriesId={seriesId}
          targetType="character"
          entityKey={c.key}
          roles={['appears']}
          empty="Not placed in any node yet (Story → Lore tab)."
        />
      </Panel>
      <Panel title="Mentioned in">
        <WhereUsed
          seriesId={seriesId}
          targetType="character"
          entityKey={c.key}
          exclude={['appears']}
          empty="No mentions or relationships yet."
        />
      </Panel>
    </div>
  )
}

export function LoreEditor({
  seriesId,
  entry: l,
  onDeleted,
}: {
  seriesId: string
  entry: Lore
  onDeleted: () => void
}) {
  const saveEntity = useSaveEntity('lore', seriesId)
  const save = (patch: S['LoreUpdate']) => saveEntity(l.id, patch)
  const { del, pending } = useDelete('lore', seriesId, 'lore', l, onDeleted)

  return (
    <div className="space-y-4 pb-10">
      <Header name={l.name} entityKey={l.key} onDelete={del} disabled={pending} />
      <Panel title="Entry">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Field label="Name">
            {(id) => (
              <TextInput
                id={id}
                value={l.name}
                onCommit={(name) => name.trim() && save({ name })}
              />
            )}
          </Field>
          <Field label="Key" hint="For [[mentions]]">
            {(id) => (
              <TextInput id={id} value={l.key} onCommit={(key) => key.trim() && save({ key })} />
            )}
          </Field>
          <Field label="Type">
            {(id) => (
              <Select
                id={id}
                value={l.type as LoreType}
                options={LORE_TYPES}
                onValueChange={(type) => type && save({ type })}
              />
            )}
          </Field>
          <Field label="Appears in">
            {(id) => (
              <ScopeSelect
                id={id}
                seriesId={seriesId}
                value={l.book_id}
                onChange={(book_id) => save({ book_id })}
              />
            )}
          </Field>
        </div>
        <p className="text-xs text-muted">{MENTION_HINT}</p>
        <ProseField
          label="Text"
          value={l.body}
          seriesId={seriesId}
          rows={8}
          always
          onCommit={(body) => save({ body })}
        />
      </Panel>
      {l.type === 'location' && (
        <Panel title="Scenes set here">
          <WhereUsed
            seriesId={seriesId}
            targetType="lore"
            entityKey={l.key}
            roles={['location']}
            empty="No node is set here yet (Story → Lore tab)."
          />
        </Panel>
      )}
      <Panel title="Mentioned in">
        <WhereUsed
          seriesId={seriesId}
          targetType="lore"
          entityKey={l.key}
          exclude={['location']}
          empty="Nothing mentions this yet."
        />
      </Panel>
    </div>
  )
}
