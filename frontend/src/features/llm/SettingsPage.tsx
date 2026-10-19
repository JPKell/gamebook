import { CircleCheck, CircleX, Plug, Plus, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { useBookGraph } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Checkbox, NumberInput, Select, TextInput } from '@/components/ui/inputs'
import { Panel } from '@/features/entities/EntityHeader'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'

import {
  type ModelInfo,
  PRESETS,
  type Provider,
  type ProviderUpdate,
  type Role,
  ROLES,
  useActivateTemplate,
  useCall,
  useCalls,
  useCosts,
  useCreateProvider,
  useDeleteProvider,
  usePreviewTemplate,
  useProviders,
  useSaveTemplate,
  useTemplates,
  useTestProvider,
  useUpdateProvider,
} from './api'

type Tab = 'providers' | 'templates' | 'calls'

export function SettingsPage() {
  const [params, setParams] = useSearchParams()
  const tab: Tab =
    (['templates', 'calls'] as const).find((t) => t === params.get('tab')) ?? 'providers'
  return (
    <div className="mx-auto max-w-6xl space-y-5 px-6 py-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <div
          role="radiogroup"
          aria-label="Settings view"
          className="ml-auto flex rounded-md border border-border bg-bg p-0.5"
        >
          {(
            [
              ['providers', 'LLM providers'],
              ['templates', 'Prompt templates'],
              ['calls', 'Call log & costs'],
            ] as const
          ).map(([v, label]) => (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={tab === v}
              onClick={() => setParams(v === 'providers' ? {} : { tab: v }, { replace: true })}
              className={cn(
                'rounded px-2.5 py-1 text-xs font-medium',
                tab === v ? 'bg-accent text-accent-fg' : 'text-muted hover:text-text',
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </header>
      {tab === 'providers' && <Providers />}
      {tab === 'templates' && <Templates />}
      {tab === 'calls' && <Calls />}
    </div>
  )
}

// ── providers ────────────────────────────────────────────────────────────

function Providers() {
  const providers = useProviders()
  const create = useCreateProvider()
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">
        Any OpenAI-compatible endpoint works: a local server, OpenAI or OpenRouter. API keys stay in
        environment variables on the machine running Gamebook Studio; only the variable's name is
        stored.
      </p>
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <Button key={p.label} size="sm" variant="outline" onClick={() => create.mutate(p.body)}>
            <Plus className="size-4" /> {p.label}
          </Button>
        ))}
      </div>
      {providers.data?.length === 0 && (
        <p className="text-sm text-muted">No providers yet. Add one above.</p>
      )}
      {(providers.data ?? []).map((p) => (
        <ProviderCard key={p.id} provider={p} />
      ))}
    </div>
  )
}

/** A variable *name* holding the key (the server's rule: keys never go in the database). */
const KEY_ENV = /^[A-Za-z_][A-Za-z0-9_]*_(KEY|TOKEN|key|token)$/

function ProviderCard({ provider: p }: { provider: Provider }) {
  const [keyError, setKeyError] = useState<string | null>(null)
  const update = useUpdateProvider()
  const remove = useDeleteProvider()
  const test = useTestProvider()
  const save = (patch: ProviderUpdate) => update.mutate({ id: p.id, ...patch })
  const models = p.models as ModelInfo[]
  const setModels = (next: ModelInfo[]) => save({ models: next })
  const result = test.data

  return (
    <Panel
      title={p.name}
      aside={
        <>
          {p.kind === 'fake' && (
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-muted">
              offline
            </span>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={() => test.mutate(p.id)}
            disabled={test.isPending}
          >
            <Plug className="size-4" /> {test.isPending ? 'Testing…' : 'Test connection'}
          </Button>
          <Button
            size="icon"
            variant="ghost"
            aria-label={`Delete ${p.name}`}
            onClick={() => window.confirm(`Delete ${p.name}?`) && remove.mutate(p.id)}
          >
            <Trash2 className="size-4" />
          </Button>
        </>
      }
    >
      {result && (
        <p
          role="status"
          className={cn(
            'flex items-center gap-1.5 text-sm',
            result.ok ? 'text-success' : 'text-danger',
          )}
        >
          {result.ok ? (
            <CircleCheck className="size-4" aria-hidden />
          ) : (
            <CircleX className="size-4" aria-hidden />
          )}
          {result.message}
          {result.latency_ms != null && (
            <span className="text-muted"> · {result.latency_ms} ms</span>
          )}
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Field label="Name">
          {(id) => (
            <TextInput id={id} value={p.name} onCommit={(name) => name.trim() && save({ name })} />
          )}
        </Field>
        {p.kind !== 'fake' && (
          <>
            <Field label="Base URL">
              {(id) => (
                <TextInput id={id} value={p.base_url} onCommit={(base_url) => save({ base_url })} />
              )}
            </Field>
            <Field
              label="API key variable (name, not the key)"
              error={keyError}
              hint={
                p.api_key_env
                  ? p.api_key_present
                    ? `${p.api_key_env} is set on the server`
                    : `${p.api_key_env} is not set on the server: add ${p.api_key_env}=your-key to the .env file next to the app and restart it`
                  : 'Leave empty if the server needs no key. Otherwise put the key in .env as LLM_API_KEY=… and enter LLM_API_KEY here.'
              }
            >
              {(id) => (
                <TextInput
                  id={id}
                  value={p.api_key_env ?? ''}
                  placeholder="e.g. LLM_API_KEY"
                  autoComplete="off"
                  onCommit={(v) => {
                    const name = v.trim()
                    if (name && !KEY_ENV.test(name)) {
                      // Most likely the key itself was pasted: don't send it anywhere.
                      setKeyError(
                        'That looks like a key, not a variable name. Keys are never stored in the app: put it in the .env file as LLM_API_KEY=… and enter LLM_API_KEY here.',
                      )
                      return
                    }
                    setKeyError(null)
                    save({ api_key_env: name || null })
                  }}
                />
              )}
            </Field>
          </>
        )}
        <Field label="Parallel calls">
          {(id) => (
            <NumberInput
              id={id}
              min={1}
              max={32}
              value={p.max_concurrency}
              onCommit={(v) => v && save({ max_concurrency: v })}
            />
          )}
        </Field>
      </div>
      <Checkbox
        label="Enabled"
        checked={p.enabled}
        onCheckedChange={(enabled) => save({ enabled })}
      />
      <div className="space-y-2">
        <h3 className="text-xs font-medium tracking-wide text-muted uppercase">Models</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-muted">
              <th className="text-left font-medium">Model id</th>
              <th className="text-left font-medium">Label</th>
              <th className="text-right font-medium">Context</th>
              <th className="text-right font-medium">$ / M in</th>
              <th className="text-right font-medium">$ / M out</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {models.map((m, i) => {
              const set = (patch: Partial<ModelInfo>) =>
                setModels(models.map((x, j) => (j === i ? { ...x, ...patch } : x)))
              return (
                <tr key={i}>
                  <td className="pr-2">
                    <TextInput
                      aria-label="Model id"
                      value={m.id}
                      onCommit={(v) => v.trim() && set({ id: v.trim() })}
                    />
                  </td>
                  <td className="pr-2">
                    <TextInput
                      aria-label="Model label"
                      value={m.label ?? ''}
                      onCommit={(label) => set({ label })}
                    />
                  </td>
                  <td className="w-28 pr-2">
                    <NumberInput
                      aria-label="Context window"
                      value={m.context_window ?? 8192}
                      onCommit={(v) => v && set({ context_window: v })}
                    />
                  </td>
                  <td className="w-24 pr-2">
                    <NumberInput
                      aria-label="Input price"
                      step="0.01"
                      value={m.input_per_mtok ?? 0}
                      onCommit={(v) => v !== null && set({ input_per_mtok: v })}
                    />
                  </td>
                  <td className="w-24 pr-2">
                    <NumberInput
                      aria-label="Output price"
                      step="0.01"
                      value={m.output_per_mtok ?? 0}
                      onCommit={(v) => v !== null && set({ output_per_mtok: v })}
                    />
                  </td>
                  <td>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`Remove ${m.id}`}
                      onClick={() => setModels(models.filter((_, j) => j !== i))}
                    >
                      <X className="size-4" />
                    </Button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setModels([...models, { id: `model-${models.length + 1}` }])}
          >
            <Plus className="size-4" /> Add model
          </Button>
          {result?.ok && (result.models ?? []).length > 0 && (
            <Select
              aria-label="Add a model from the server"
              className="h-7 w-auto py-0 text-xs"
              value={null}
              placeholder="+ Add from the server's list…"
              options={(result.models ?? [])
                .filter((id) => !models.some((m) => m.id === id))
                .map((id) => ({ value: id, label: id }))}
              onValueChange={(id) => id && setModels([...models, { id }])}
            />
          )}
        </div>
      </div>
    </Panel>
  )
}

// ── templates ────────────────────────────────────────────────────────────

function Templates() {
  const templates = useTemplates()
  const save = useSaveTemplate()
  const activate = useActivateTemplate()
  const preview = usePreviewTemplate()
  const [role, setRole] = useState<Role>('writer')
  const versions = (templates.data ?? []).filter((t) => t.role === role)
  const active = versions.find((t) => t.is_active)
  // The editor below is keyed by role + active version, so it restarts from the
  // active text whenever either changes.
  const [edit, setEdit] = useState<{
    key: string
    system: string
    user: string
    notes: string
  } | null>(null)
  const editKey = `${role}:${active?.id ?? ''}`
  const current =
    edit?.key === editKey
      ? edit
      : { key: editKey, system: active?.system ?? '', user: active?.user ?? '', notes: '' }
  const { system, user, notes } = current
  const setSystem = (v: string) => setEdit({ ...current, system: v })
  const setUser = (v: string) => setEdit({ ...current, user: v })
  const setNotes = (v: string) => setEdit({ ...current, notes: v })
  const lastBookId = useUiStore((s) => s.lastBookId)
  const graph = useBookGraph(lastBookId ?? undefined)
  const [variantId, setVariantId] = useState<string | null>(null)
  const variants = (graph.data?.nodes ?? []).flatMap((n) =>
    n.variants.map((v) => ({
      value: v.id,
      label: v.label === 'Default' ? n.title : `${n.title} (${v.label})`,
    })),
  )
  const dirty = active && (system !== active.system || user !== active.user)

  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="Roles" className="flex gap-1 border-b border-border">
        {ROLES.map((r) => (
          <button
            key={r.key}
            type="button"
            role="tab"
            aria-selected={role === r.key}
            onClick={() => {
              if (dirty && !window.confirm('Discard your unsaved changes to this template?')) return
              setEdit(null)
              setRole(r.key)
            }}
            className={cn(
              'relative px-3 py-2 text-sm font-medium',
              role === r.key
                ? 'text-accent after:absolute after:inset-x-1 after:-bottom-px after:h-0.5 after:rounded after:bg-accent'
                : 'text-muted hover:text-text',
            )}
          >
            {r.label}
          </button>
        ))}
      </div>
      <p className="text-sm text-muted">
        {ROLES.find((r) => r.key === role)?.hint} Templates use Jinja2:{' '}
        <code>{'{{ ctx.node.beat_notes }}'}</code>, <code>{'{{ draft }}'}</code>,{' '}
        <code>{'{% for i in issues %}'}</code>… Saving creates a new version; older versions stay
        available.
      </p>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="space-y-3">
          <Field label="System prompt">
            {(id) => (
              <textarea
                id={id}
                rows={5}
                value={system}
                onChange={(e) => setSystem(e.target.value)}
                className="w-full rounded-md border border-border bg-bg p-2 font-mono text-xs"
              />
            )}
          </Field>
          <Field label="User prompt">
            {(id) => (
              <textarea
                id={id}
                rows={16}
                value={user}
                onChange={(e) => setUser(e.target.value)}
                className="w-full rounded-md border border-border bg-bg p-2 font-mono text-xs"
              />
            )}
          </Field>
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Version notes" className="min-w-64 flex-1">
              {(id) => (
                <TextInput id={id} value={notes} onCommit={setNotes} placeholder="What changed?" />
              )}
            </Field>
            <Button
              disabled={!dirty || save.isPending}
              onClick={() =>
                save.mutate({ role, system, user, notes }, { onSuccess: () => setEdit(null) })
              }
            >
              Save as version {(versions[0]?.version ?? 0) + 1}
            </Button>
          </div>
        </div>
        <aside className="space-y-2">
          <h3 className="text-xs font-medium tracking-wide text-muted uppercase">Versions</h3>
          <ul className="space-y-1 text-sm">
            {versions.map((t) => (
              <li key={t.id} className="flex items-center gap-2">
                <span className="font-medium">v{t.version}</span>
                <span className="min-w-0 flex-1 truncate text-xs text-muted">{t.notes}</span>
                {t.is_active ? (
                  <span className="rounded-full bg-success/12 px-2 text-xs text-success">
                    active
                  </span>
                ) : (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => activate.mutate(t.id, { onSuccess: () => setEdit(null) })}
                  >
                    Use
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </aside>
      </div>
      <Panel title="Preview against a section">
        <div className="flex flex-wrap items-center gap-2">
          <Select
            aria-label="Section to preview with"
            className="w-auto"
            value={variantId}
            placeholder={lastBookId ? 'Choose a section…' : 'Open a book first'}
            options={variants}
            onValueChange={setVariantId}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={!variantId}
            onClick={() =>
              variantId && preview.mutate({ role, variant_id: variantId, system, user })
            }
          >
            Render
          </Button>
          {preview.data && !preview.data.error && (
            <span className="text-xs text-muted">
              ≈ {preview.data.tokens.toLocaleString()} tokens
            </span>
          )}
        </div>
        {preview.data?.error && <p className="text-sm text-danger">{preview.data.error}</p>}
        {preview.data && !preview.data.error && (
          <pre className="max-h-96 overflow-auto rounded-md bg-surface-2 p-3 text-xs whitespace-pre-wrap">
            <span className="text-muted">— system —{'\n'}</span>
            {preview.data.system}
            <span className="text-muted">
              {'\n\n'}— user —{'\n'}
            </span>
            {preview.data.user}
          </pre>
        )}
      </Panel>
    </div>
  )
}

// ── call log ─────────────────────────────────────────────────────────────

function Calls() {
  const [role, setRole] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [open, setOpen] = useState<string | null>(null)
  const calls = useCalls({ role: role ?? undefined, status: status ?? undefined, offset })
  const costs = useCosts(null)
  const total = calls.data?.total ?? 0
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-border bg-surface p-3">
          <dt className="text-xs text-muted">Total spent</dt>
          <dd className="text-2xl font-semibold tabular-nums">
            ${(costs.data?.total_usd ?? 0).toFixed(4)}
          </dd>
        </div>
        {(costs.data?.by_role ?? []).map((r) => (
          <div key={r.key} className="rounded-xl border border-border bg-surface p-3">
            <dt className="text-xs text-muted capitalize">{r.key}</dt>
            <dd className="text-lg font-semibold tabular-nums">
              ${r.cost_usd.toFixed(4)}{' '}
              <span className="text-xs font-normal text-muted">· {r.calls} calls</span>
            </dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap items-center gap-2">
        <Select
          aria-label="Role"
          className="w-40"
          value={role}
          placeholder="All roles"
          options={ROLES.map((r) => ({ value: r.key, label: r.label }))}
          onValueChange={(v) => {
            setRole(v)
            setOffset(0)
          }}
        />
        <Select
          aria-label="Status"
          className="w-36"
          value={status}
          placeholder="Any status"
          options={[
            { value: 'ok', label: 'OK' },
            { value: 'error', label: 'Errors' },
          ]}
          onValueChange={(v) => {
            setStatus(v)
            setOffset(0)
          }}
        />
        <span className="ml-auto text-xs text-muted tabular-nums">
          {total ? `${offset + 1}–${Math.min(total, offset + 25)} of ${total}` : 'No calls yet'}
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={offset === 0}
          onClick={() => setOffset((o) => Math.max(0, o - 25))}
        >
          Previous
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={offset + 25 >= total}
          onClick={() => setOffset((o) => o + 25)}
        >
          Next
        </Button>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-muted">
            <th className="text-left font-medium">When</th>
            <th className="text-left font-medium">Role</th>
            <th className="text-left font-medium">Model</th>
            <th className="text-right font-medium">Tokens in / out</th>
            <th className="text-right font-medium">Time</th>
            <th className="text-right font-medium">Cost</th>
            <th className="text-left font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {(calls.data?.calls ?? []).map((c) => (
            <tr
              key={c.id}
              className={cn('cursor-pointer hover:bg-surface-2', open === c.id && 'bg-accent/8')}
              onClick={() => setOpen(open === c.id ? null : c.id)}
            >
              <td className="py-1.5 tabular-nums">{new Date(c.created_at).toLocaleString()}</td>
              <td className="capitalize">{c.role}</td>
              <td className="truncate">{c.model}</td>
              <td className="text-right tabular-nums">
                {c.prompt_tokens.toLocaleString()} / {c.completion_tokens.toLocaleString()}
              </td>
              <td className="text-right tabular-nums">{(c.latency_ms / 1000).toFixed(1)} s</td>
              <td className="text-right tabular-nums">${c.cost_usd.toFixed(4)}</td>
              <td className={c.status === 'error' ? 'text-danger' : 'text-muted'}>
                {c.status === 'error' ? c.error : 'ok'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {open && <CallDetail id={open} onClose={() => setOpen(null)} />}
    </div>
  )
}

function CallDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const call = useCall(id)
  const c = call.data
  if (!c) return null
  return (
    <Panel
      title={`${c.role} · ${c.model} · template v${c.template_version ?? '?'}`}
      aside={
        <Button size="icon" variant="ghost" aria-label="Close call" onClick={onClose}>
          <X className="size-4" />
        </Button>
      }
    >
      {c.messages.map((m, i) => (
        <div key={i} className="space-y-1">
          <h3 className="text-xs font-medium tracking-wide text-muted uppercase">
            {String(m.role)}
          </h3>
          <pre className="max-h-72 overflow-auto rounded-md bg-surface-2 p-3 text-xs whitespace-pre-wrap">
            {String(m.content)}
          </pre>
        </div>
      ))}
      <div className="space-y-1">
        <h3 className="text-xs font-medium tracking-wide text-muted uppercase">Response</h3>
        <pre className="max-h-72 overflow-auto rounded-md bg-surface-2 p-3 text-xs whitespace-pre-wrap">
          {c.response || c.error}
        </pre>
      </div>
    </Panel>
  )
}
