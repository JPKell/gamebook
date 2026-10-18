import {
  CircleAlert,
  CircleX,
  Copy,
  Dices,
  FlaskConical,
  MoreHorizontal,
  Plus,
  Scale,
  Star,
  Trash2,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router'

import { useBook, useEntities, useFlags, useRuleSystems, useSeriesList } from '@/api/queries'
import { rulesVocabulary, type Vocabulary, VocabularyContext } from '@/components/gbx/vocabulary'
import { Button } from '@/components/ui/button'
import { buttonVariants } from '@/components/ui/button-variants'
import { EmptyState } from '@/components/ui/empty'
import { Select } from '@/components/ui/inputs'
import { Menu, MenuItem, MenuSeparator } from '@/components/ui/menu'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'

import {
  useCreateRuleSystem,
  useDeleteRuleSystem,
  useRuleProblems,
  useSaveDefinition,
  useTierView,
  useUpdateRuleSystemMeta,
} from './api'
import { CombatLab } from './CombatLab'
import { addTier, type RuleSystemDef } from './defs'
import { TierEditor } from './TierEditor'

/** /mechanics — open the series of the last book, or the first series. */
export function MechanicsIndex() {
  const lastBookId = useUiStore((s) => s.lastBookId)
  const book = useBook(lastBookId ?? undefined)
  const series = useSeriesList()
  if (lastBookId && book.isPending) return <p className="p-6 text-muted">Loading…</p>
  const seriesId = book.data?.series_id ?? series.data?.[0]?.id
  if (seriesId) return <Navigate to={`/mechanics/${seriesId}`} replace />
  if (series.isPending) return <p className="p-6 text-muted">Loading…</p>
  return (
    <EmptyState
      icon={Dices}
      title="No series yet"
      action={
        <Link to="/library" className={buttonVariants()}>
          Go to the Library
        </Link>
      }
    >
      Rules belong to a series. Create one in the Library first.
    </EmptyState>
  )
}

export function MechanicsPage() {
  const { seriesId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const seriesList = useSeriesList()
  const systems = useRuleSystems(seriesId)

  const rs =
    systems.data?.find((r) => r.id === params.get('rs')) ??
    systems.data?.find((r) => r.is_active) ??
    systems.data?.[0]
  const def = rs?.definition as RuleSystemDef | undefined
  const tierKey = def?.tiers.find((t) => t.key === params.get('tier'))?.key ?? def?.tiers[0]?.key
  const mode = params.get('view') === 'lab' ? 'lab' : 'rules'
  const set = (patch: Record<string, string | null>) =>
    setParams(
      (p) => {
        for (const [k, v] of Object.entries(patch)) {
          if (v === null) p.delete(k)
          else p.set(k, v)
        }
        return p
      },
      { replace: true },
    )

  if (systems.isPending) return <p className="p-6 text-muted">Loading rules…</p>
  if (systems.isError || !rs || !def || !tierKey)
    return (
      <EmptyState
        icon={Dices}
        title="No rule system"
        action={
          <Link className="text-accent underline" to="/library">
            Back to the Library
          </Link>
        }
      >
        This series has no rule systems.
      </EmptyState>
    )

  return (
    <div className="mx-auto max-w-6xl space-y-5 px-6 py-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Mechanics</h1>
        <Select
          aria-label="Series"
          value={seriesId}
          onValueChange={(id) => id && navigate(`/mechanics/${id}`)}
          options={(seriesList.data ?? []).map((s) => ({ value: s.id, label: s.title }))}
          className="w-auto"
        />
        <Select
          aria-label="Rule system"
          value={rs.id}
          onValueChange={(id) => id && set({ rs: id, tier: null })}
          options={(systems.data ?? []).map((r) => ({
            value: r.id,
            label: `${r.name}${r.is_active ? ' (active)' : ''}`,
          }))}
          className="w-auto"
        />
        {rs.is_active ? (
          <span className="flex items-center gap-1 rounded-full bg-success/12 px-2.5 py-1 text-xs font-medium text-success">
            <Star className="size-3.5" aria-hidden /> Active — books use these rules
          </span>
        ) : (
          <span className="rounded-full bg-surface-2 px-2.5 py-1 text-xs text-muted">
            Draft — not used by books
          </span>
        )}
        <SystemMenu
          seriesId={seriesId}
          rs={rs}
          def={def}
          onSelect={(id) => set({ rs: id, tier: null })}
        />
      </header>

      <RuleProblems
        rsId={rs.id}
        onTier={(t) => set({ tier: t, view: null })}
        tiers={def.tiers.map((t) => t.key)}
      />

      <div className="flex flex-wrap items-center gap-2 border-b border-border">
        <div role="tablist" aria-label="Tiers" className="flex gap-1">
          {def.tiers.map((t) => (
            <button
              key={t.key}
              role="tab"
              type="button"
              aria-selected={t.key === tierKey}
              onClick={() => set({ tier: t.key })}
              className={cn(
                'relative px-3 py-2 text-sm font-medium transition-colors',
                t.key === tierKey
                  ? 'text-accent after:absolute after:inset-x-1 after:-bottom-px after:h-0.5 after:rounded after:bg-accent'
                  : 'text-muted hover:text-text',
              )}
            >
              {t.label}
              {t.parent && (
                <span className="ml-1 text-[11px] font-normal text-muted">
                  +{def.tiers.find((p) => p.key === t.parent)?.label}
                </span>
              )}
            </button>
          ))}
        </div>
        <AddTierButton
          seriesId={seriesId}
          rsId={rs.id}
          def={def}
          onAdded={(key) => set({ tier: key })}
        />
        <div
          role="radiogroup"
          aria-label="View"
          className="mb-1 ml-auto flex rounded-md border border-border bg-bg p-0.5"
        >
          {(
            [
              ['rules', 'Rules', Scale],
              ['lab', 'Combat lab', FlaskConical],
            ] as const
          ).map(([v, label, Icon]) => (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={mode === v}
              onClick={() => set({ view: v === 'rules' ? null : v })}
              className={cn(
                'flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium',
                mode === v ? 'bg-accent text-accent-fg' : 'text-muted hover:text-text',
              )}
            >
              <Icon className="size-3.5" aria-hidden /> {label}
            </button>
          ))}
        </div>
      </div>

      <TierWorkspace
        key={`${rs.id}:${tierKey}`}
        seriesId={seriesId}
        rsId={rs.id}
        def={def}
        tierKey={tierKey}
        mode={mode}
        onTierDeleted={() => set({ tier: null })}
      />
    </div>
  )
}

function TierWorkspace({
  seriesId,
  rsId,
  def,
  tierKey,
  mode,
  onTierDeleted,
}: {
  seriesId: string
  rsId: string
  def: RuleSystemDef
  tierKey: string
  mode: 'rules' | 'lab'
  onTierDeleted: () => void
}) {
  const view = useTierView(rsId, tierKey)
  const save = useSaveDefinition(seriesId, rsId)
  const items = useEntities('items', seriesId)
  const flags = useFlags(seriesId)
  const vocab = useMemo<Vocabulary>(() => {
    const rules = rulesVocabulary({ definition: def } as never)
    const stats = view.data?.stats.map((s) => ({ key: s.key, label: s.label })) ?? rules.stats
    return {
      bookId: '',
      seriesId,
      ruleSystemId: rsId,
      ...rules,
      stats,
      items: (items.data ?? []).map((i) => ({ key: i.key, label: i.name })),
      flags: (flags.data ?? []).map((f) => ({ key: f.flag, label: f.flag })),
      nodes: [],
    }
  }, [def, view.data, seriesId, rsId, items.data, flags.data])

  if (!view.data)
    return (
      <p className="text-muted">
        {view.isError ? 'This tier has an invalid parent chain.' : 'Loading…'}
      </p>
    )
  return (
    <VocabularyContext.Provider value={vocab}>
      {mode === 'rules' ? (
        <TierEditor
          def={def}
          tierKey={tierKey}
          view={view.data}
          save={(next) => save.mutate(next)}
          onDeleted={onTierDeleted}
        />
      ) : (
        <CombatLab
          seriesId={seriesId}
          ruleSystemId={rsId}
          def={def}
          tier={tierKey}
          view={view.data}
        />
      )}
    </VocabularyContext.Provider>
  )
}

function AddTierButton({
  seriesId,
  rsId,
  def,
  onAdded,
}: {
  seriesId: string
  rsId: string
  def: RuleSystemDef
  onAdded: (key: string) => void
}) {
  const save = useSaveDefinition(seriesId, rsId)
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => {
        const label = window
          .prompt('Name of the new tier (it inherits everything from the last tier)')
          ?.trim()
        if (!label) return
        const { def: next, key } = addTier(def, label)
        save.mutate(next, { onSuccess: () => onAdded(key) })
      }}
    >
      <Plus className="size-4" /> Add tier
    </Button>
  )
}

function SystemMenu({
  seriesId,
  rs,
  def,
  onSelect,
}: {
  seriesId: string
  rs: { id: string; name: string; is_active: boolean }
  def: RuleSystemDef
  onSelect: (id: string) => void
}) {
  const create = useCreateRuleSystem(seriesId)
  const update = useUpdateRuleSystemMeta(seriesId)
  const remove = useDeleteRuleSystem(seriesId)
  return (
    <Menu
      trigger={
        <Button variant="ghost" size="icon" aria-label="Rule system actions">
          <MoreHorizontal className="size-4" />
        </Button>
      }
    >
      <MenuItem
        icon={<Star />}
        disabled={rs.is_active}
        onSelect={() => update.mutate({ id: rs.id, is_active: true })}
      >
        Make active (books use it)
      </MenuItem>
      <MenuItem
        icon={<Scale />}
        onSelect={() => {
          const name = window.prompt('Rename rule system', rs.name)?.trim()
          if (name) update.mutate({ id: rs.id, name })
        }}
      >
        Rename…
      </MenuItem>
      <MenuSeparator />
      <MenuItem
        icon={<Copy />}
        onSelect={() =>
          create.mutate(
            { name: `${rs.name} (copy)`, definition: def },
            { onSuccess: (r) => onSelect(r.id) },
          )
        }
      >
        Duplicate as a draft (for experiments)
      </MenuItem>
      <MenuItem
        icon={<Plus />}
        onSelect={() =>
          create.mutate({ name: 'New rules (template)' }, { onSuccess: (r) => onSelect(r.id) })
        }
      >
        New from the starter template
      </MenuItem>
      <MenuSeparator />
      <MenuItem
        icon={<Trash2 />}
        danger
        onSelect={() => {
          const warn = rs.is_active
            ? ' Books will have no rules until another system is made active.'
            : ''
          if (window.confirm(`Delete “${rs.name}”?${warn}`)) remove.mutate(rs.id)
        }}
      >
        Delete…
      </MenuItem>
    </Menu>
  )
}

function RuleProblems({
  rsId,
  tiers,
  onTier,
}: {
  rsId: string
  tiers: string[]
  onTier: (tier: string) => void
}) {
  const problems = useRuleProblems(rsId)
  const [open, setOpen] = useState(false)
  const data = problems.data
  if (!data || data.problems.length === 0) return null
  const tierOf = (field: string | null | undefined) => {
    const m = /^tiers\.([^.]+)/.exec(field ?? '')
    return m && tiers.includes(m[1]!) ? m[1]! : null
  }
  return (
    <section
      aria-label="Rule problems"
      className="rounded-lg border border-warning/40 bg-warning/8 px-4 py-2 text-sm"
    >
      <button
        type="button"
        className="flex items-center gap-3"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {data.counts.errors > 0 && (
          <span className="flex items-center gap-1 text-danger">
            <CircleX className="size-4" aria-hidden /> {data.counts.errors} error
            {data.counts.errors === 1 ? '' : 's'}
          </span>
        )}
        {data.counts.warnings > 0 && (
          <span className="flex items-center gap-1 text-warning">
            <CircleAlert className="size-4" aria-hidden /> {data.counts.warnings} warning
            {data.counts.warnings === 1 ? '' : 's'}
          </span>
        )}
        <span className="text-muted">{open ? 'Hide' : 'Show'} details</span>
      </button>
      {open && (
        <ul className="mt-2 space-y-1">
          {data.problems.map((p, i) => {
            const tier = tierOf(p.field)
            return (
              <li key={i} className="flex items-start gap-2">
                {p.severity === 'error' ? (
                  <CircleX className="mt-0.5 size-4 shrink-0 text-danger" aria-label="error" />
                ) : (
                  <CircleAlert
                    className="mt-0.5 size-4 shrink-0 text-warning"
                    aria-label="warning"
                  />
                )}
                {tier ? (
                  <button
                    type="button"
                    className="text-left hover:underline"
                    onClick={() => onTier(tier)}
                  >
                    {p.message}
                  </button>
                ) : (
                  <span>{p.message}</span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
