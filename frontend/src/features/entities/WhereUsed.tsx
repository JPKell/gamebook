import { Link } from 'react-router'

import { useWhereUsed } from './api'

const ROLE_LABELS: Record<string, string> = {
  placement: 'found here',
  shop: 'sold in a shop',
  'effect.give': 'given',
  'effect.take': 'taken away',
  'effect.equip': 'equipped',
  condition: 'required by a condition',
  modifier: 'modifier',
  loot: 'dropped as loot',
  table: 'random table result',
  encounter: 'encounter',
  outcome: 'choice destination',
  formula: 'formula',
  mention: 'mentioned',
  appears: 'appears',
  location: 'set here',
  relationship: 'relationship',
  lore: 'lore link',
}

type Ref = { source_id: string; book_id?: string | null }

/** Where to open a non-node source (other entities, story beats). */
const SOURCE_LINKS: Record<string, ((seriesId: string, r: Ref) => string) | undefined> = {
  character: (s, r) => `/lore/${s}?tab=characters&id=${r.source_id}`,
  lore: (s, r) => `/lore/${s}?tab=entries&id=${r.source_id}`,
  beat: (s, r) => `/lore/${s}?tab=outline&book=${r.book_id ?? ''}`,
  enemy: (s, r) => `/enemies/${s}?id=${r.source_id}`,
  item: (s, r) => `/items/${s}?id=${r.source_id}`,
  table: (s, r) => `/enemies/${s}?tab=tables&id=${r.source_id}`,
}

/** Every place an entity is referenced, linking straight to the node or entity. */
export function WhereUsed({
  seriesId,
  targetType,
  entityKey,
  showTotal = false,
  roles,
  exclude,
  empty = 'Not used anywhere yet.',
}: {
  seriesId: string
  targetType: string
  entityKey: string
  showTotal?: boolean
  /** Only these roles (e.g. ['mention']). */
  roles?: string[]
  /** Leave these roles out. */
  exclude?: string[]
  empty?: string
}) {
  const used = useWhereUsed(seriesId, targetType, entityKey)
  if (used.isPending) return <p className="text-sm text-muted">Loading…</p>
  const refs = (used.data?.refs ?? []).filter(
    (r) => (!roles || roles.includes(r.role)) && !exclude?.includes(r.role),
  )
  return (
    <div className="space-y-2">
      {showTotal && (
        <p className="text-sm">
          <span className="text-2xl font-semibold">
            {used.data?.total_qty ?? 0}
            {used.data?.unlimited && '+'}
          </span>{' '}
          <span className="text-muted">
            in the game across {refs.length} reference{refs.length === 1 ? '' : 's'}
            {used.data?.unlimited && ', plus unlimited stock in a shop'}
          </span>
        </p>
      )}
      {refs.length === 0 ? (
        <p className="text-sm text-muted">{empty}</p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border text-sm">
          {refs.map((r, i) => (
            <li key={i} className="flex items-center gap-3 px-3 py-2">
              <span className="min-w-0 flex-1 truncate">
                {r.node_id && r.book_id ? (
                  <Link
                    to={`/story/${r.book_id}?node=${r.node_id}`}
                    className="font-medium text-accent hover:underline"
                  >
                    {r.node_title || 'Untitled node'}
                  </Link>
                ) : SOURCE_LINKS[r.source_type] ? (
                  <Link
                    to={SOURCE_LINKS[r.source_type]!(seriesId, r)}
                    className="font-medium text-accent hover:underline"
                  >
                    {r.source_label ?? r.source_type}
                  </Link>
                ) : (
                  <span className="font-medium">{r.source_label ?? r.source_type}</span>
                )}
                {r.book_title && <span className="text-muted"> · {r.book_title}</span>}
              </span>
              <span className="shrink-0 text-xs text-muted">{ROLE_LABELS[r.role] ?? r.role}</span>
              {r.qty != null && (
                <span className="w-10 shrink-0 text-right tabular-nums">×{r.qty}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
