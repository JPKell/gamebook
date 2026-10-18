import { useState } from 'react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { NumberInput, Select } from '@/components/ui/inputs'
import {
  type ModelInfo,
  type Role,
  ROLES,
  useProviders,
  useSaveWritingSettings,
  useWritingSettings,
  type WritingSettings,
} from '@/features/llm/api'

/** Models per role, pass threshold, rewrite iterations and context budget (per series). */
export function PipelineSettings({
  seriesId,
  open,
  onOpenChange,
}: {
  seriesId: string
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const settings = useWritingSettings(seriesId)
  // Mounted only while open, so every opening starts from the saved settings.
  if (!open || !settings.data) return null
  return <SettingsForm seriesId={seriesId} initial={settings.data} onOpenChange={onOpenChange} />
}

function SettingsForm({
  seriesId,
  initial,
  onOpenChange,
}: {
  seriesId: string
  initial: WritingSettings
  onOpenChange: (o: boolean) => void
}) {
  const providers = useProviders()
  const save = useSaveWritingSettings(seriesId)
  const [draft, setDraft] = useState<WritingSettings>(initial)
  const enabled = (providers.data ?? []).filter((p) => p.enabled)
  const setRole = (role: Role, patch: Partial<NonNullable<WritingSettings['roles']>[Role]>) =>
    setDraft((d) => ({ ...d, roles: { ...d.roles, [role]: { ...d.roles?.[role], ...patch } } }))

  return (
    <Dialog
      open
      onOpenChange={onOpenChange}
      title="Pipeline settings"
      description="Which model plays each role in this series. Roles left unset use the writer's model."
      className="w-[min(760px,calc(100vw-2rem))]"
      footer={
        <Button
          onClick={() => save.mutate(draft, { onSuccess: () => onOpenChange(false) })}
          disabled={save.isPending}
        >
          Save
        </Button>
      }
    >
      <div className="space-y-4">
        {enabled.length === 0 && (
          <p className="text-sm text-warning">
            No LLM providers yet.{' '}
            <Link to="/settings" className="text-accent underline">
              Add one in Settings
            </Link>
            .
          </p>
        )}
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-muted">
              <th className="text-left font-medium">Role</th>
              <th className="text-left font-medium">Provider</th>
              <th className="text-left font-medium">Model</th>
              <th className="text-right font-medium">Temperature</th>
              <th className="text-right font-medium">Max tokens</th>
            </tr>
          </thead>
          <tbody>
            {ROLES.map((r) => {
              const rm = draft.roles?.[r.key]
              const provider = enabled.find((p) => p.id === rm?.provider_id)
              const models = (provider?.models ?? []) as ModelInfo[]
              return (
                <tr key={r.key}>
                  <td className="py-1 pr-2 font-medium" title={r.hint}>
                    {r.label}
                  </td>
                  <td className="pr-2">
                    <Select
                      aria-label={`${r.label} provider`}
                      value={rm?.provider_id ?? null}
                      placeholder={r.key === 'writer' ? 'Choose…' : 'Same as writer'}
                      options={enabled.map((p) => ({ value: p.id, label: p.name }))}
                      onValueChange={(provider_id) => setRole(r.key, { provider_id, model: null })}
                    />
                  </td>
                  <td className="pr-2">
                    <Select
                      aria-label={`${r.label} model`}
                      value={rm?.model ?? null}
                      placeholder={provider ? 'Choose…' : '—'}
                      disabled={!provider}
                      options={models.map((m) => ({ value: m.id, label: m.label || m.id }))}
                      onValueChange={(model) => setRole(r.key, { model })}
                    />
                  </td>
                  <td className="w-24 pr-2">
                    <NumberInput
                      aria-label={`${r.label} temperature`}
                      step="0.1"
                      min={0}
                      max={2}
                      value={rm?.temperature ?? 0.7}
                      onCommit={(t) => t !== null && setRole(r.key, { temperature: t })}
                    />
                  </td>
                  <td className="w-24">
                    <NumberInput
                      aria-label={`${r.label} max tokens`}
                      min={16}
                      value={rm?.max_tokens ?? 1500}
                      onCommit={(t) => t && setRole(r.key, { max_tokens: t })}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div className="grid grid-cols-3 gap-3">
          <Field
            label="Pass score (0–10)"
            hint="Drafts the critic scores at least this skip further edits."
          >
            {(id) => (
              <NumberInput
                id={id}
                step="0.5"
                min={0}
                max={10}
                value={draft.pass_threshold ?? 7.5}
                onCommit={(v) => v !== null && setDraft({ ...draft, pass_threshold: v })}
              />
            )}
          </Field>
          <Field label="Max rewrites" hint="Editor passes after the first draft.">
            {(id) => (
              <NumberInput
                id={id}
                min={0}
                max={6}
                value={draft.max_iterations ?? 2}
                onCommit={(v) => v !== null && setDraft({ ...draft, max_iterations: v })}
              />
            )}
          </Field>
          <Field label="Context budget (tokens)" hint="Low-priority context is trimmed to fit.">
            {(id) => (
              <NumberInput
                id={id}
                min={500}
                value={draft.context_tokens ?? 6000}
                onCommit={(v) => v && setDraft({ ...draft, context_tokens: v })}
              />
            )}
          </Field>
        </div>
        <p className="text-xs text-muted">
          Prompts for each role are edited in{' '}
          <Link to="/settings?tab=templates" className="text-accent underline">
            Settings → Prompt templates
          </Link>
          .
        </p>
      </div>
    </Dialog>
  )
}
