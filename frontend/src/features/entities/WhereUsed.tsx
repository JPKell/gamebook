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
}

/** Every place an entity is referenced, linking straight to the node. */
export function WhereUsed({
  seriesId,
  targetType,
  entityKey,
  showTotal = false,
}: {
  seriesId: string
  targetType: string
  entityKey: string
  showTotal?: boolean
}) {
  const used = useWhereUsed(seriesId, targetType, entityKey)
  if (used.isPending) return <p className="text-sm text-muted">Loading…</p>
  const refs = used.data?.refs ?? []
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
        <p className="text-sm text-muted">Not used anywhere yet.</p>
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
