import { Download } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { buttonVariants } from '@/components/ui/button-variants'
import { Select } from '@/components/ui/inputs'

import { STATUS_LABELS, useShotList, useUpdatePlacement } from './api'

/** Every placement with its brief, printed size and status; shot list exports. */
export function CommissioningView({ seriesId }: { seriesId: string }) {
  const shots = useShotList(seriesId)
  const update = useUpdatePlacement(seriesId)
  const [status, setStatus] = useState<string | null>(null)
  const rows = (shots.data ?? []).filter((r) => !status || r.status === status)
  const counts = Object.fromEntries(
    Object.keys(STATUS_LABELS).map((k) => [
      k,
      (shots.data ?? []).filter((r) => r.status === k).length,
    ]),
  )
  const href = (format: string) =>
    `/api/series/${seriesId}/shot-list?format=${format}${status ? `&status=${status}` : ''}`
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Select
          aria-label="Filter by status"
          value={status}
          placeholder={`All (${shots.data?.length ?? 0})`}
          options={Object.entries(STATUS_LABELS).map(([value, label]) => ({
            value,
            label: `${label} (${counts[value]})`,
          }))}
          onValueChange={setStatus}
          className="w-auto"
        />
        <a
          href={href('md')}
          download
          className={buttonVariants({ variant: 'outline', size: 'sm', className: 'ml-auto' })}
        >
          <Download className="size-4" /> Shot list (Markdown)
        </a>
        <a
          href={href('csv')}
          download
          className={buttonVariants({ variant: 'outline', size: 'sm' })}
        >
          <Download className="size-4" /> CSV
        </a>
      </div>
      {update.error && <p className="text-xs text-danger">{update.error.message}</p>}
      {shots.data && rows.length === 0 ? (
        <p className="text-sm text-muted">
          Nothing here. Add placeholders with a brief from a section's Art tab, Book art, or an
          entity's portrait to plan the art you need.
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted">
              <th className="py-1 font-medium">Piece</th>
              <th className="font-medium">Book</th>
              <th className="font-medium">Brief</th>
              <th className="font-medium">Printed size</th>
              <th className="font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => (
              <tr key={r.placement_id} className="align-top">
                <td className="py-1.5 pr-3">
                  {r.node_id && r.book_id ? (
                    <Link
                      to={`/story/${r.book_id}?node=${r.node_id}`}
                      className="text-accent hover:underline"
                    >
                      {r.target_label}
                    </Link>
                  ) : (
                    r.target_label
                  )}
                  {!r.has_asset && <span className="ml-1 text-xs text-muted">(placeholder)</span>}
                </td>
                <td className="pr-3 text-muted">{r.book_title ?? '—'}</td>
                <td className="max-w-sm pr-3 whitespace-pre-wrap">
                  {r.brief || <span className="text-muted">—</span>}
                </td>
                <td className="pr-3 text-xs text-muted tabular-nums">
                  {r.width_mm} × {r.height_mm} mm
                  <br />
                  {r.needed_px[0]} × {r.needed_px[1]} px
                </td>
                <td>
                  <Select
                    aria-label={`Status of ${r.target_label}`}
                    value={r.status}
                    options={Object.entries(STATUS_LABELS).map(([value, label]) => ({
                      value,
                      label,
                    }))}
                    onValueChange={(s) =>
                      s && update.mutate({ id: r.placement_id, status: s as never })
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
