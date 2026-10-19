import { Search } from 'lucide-react'
import { useState } from 'react'

import { Dialog } from '@/components/ui/dialog'

import { type Asset, useAssets } from './api'
import { UploadZone } from './UploadZone'

/** Choose an image from the library (or upload one). */
export function AssetPicker({
  seriesId,
  open,
  onOpenChange,
  onPick,
  title = 'Choose an image',
}: {
  seriesId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onPick: (asset: Asset) => void
  title?: string
}) {
  const assets = useAssets(open ? seriesId : undefined)
  const [q, setQ] = useState('')
  const needle = q.trim().toLowerCase()
  const shown = (assets.data ?? []).filter(
    (a) =>
      !needle ||
      a.filename.toLowerCase().includes(needle) ||
      a.alt_text.toLowerCase().includes(needle) ||
      a.tags.some((t) => t.includes(needle)),
  )
  const pick = (a: Asset) => {
    onPick(a)
    onOpenChange(false)
  }
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      className="w-[min(760px,calc(100vw-2rem))]"
    >
      <div className="space-y-3">
        <UploadZone
          seriesId={seriesId}
          compact
          onUploaded={(done) => done.length === 1 && pick(done[0]!)}
        />
        <label className="flex items-center gap-2 rounded-md border border-border px-2">
          <Search className="size-4 text-muted" aria-hidden />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter by name, alt text or tag"
            aria-label="Filter images"
            className="w-full bg-transparent py-1.5 text-sm outline-none"
          />
        </label>
        {assets.data && shown.length === 0 && (
          <p className="text-sm text-muted">
            {assets.data.length ? 'No matches.' : 'The library is empty.'}
          </p>
        )}
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4" aria-label="Library">
          {shown.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                onClick={() => pick(a)}
                className="group w-full overflow-hidden rounded-lg border border-border text-left hover:border-accent focus-visible:border-accent"
                aria-label={`Use ${a.filename}`}
              >
                <img
                  src={a.thumb_url}
                  alt={a.alt_text}
                  loading="lazy"
                  className="aspect-square w-full bg-surface-2 object-cover"
                />
                <span className="block truncate px-1.5 py-1 text-[11px] text-muted group-hover:text-text">
                  {a.filename} · {a.width_px}×{a.height_px}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </Dialog>
  )
}
