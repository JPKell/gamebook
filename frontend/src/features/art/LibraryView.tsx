import { ExternalLink, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty'
import { Field } from '@/components/ui/field'
import { TextArea, TextInput } from '@/components/ui/inputs'
import { Panel } from '@/features/entities/EntityHeader'
import { cn } from '@/lib/utils'

import {
  type Asset,
  ROLE_LABELS,
  useAssets,
  useAssetUses,
  useDeleteAsset,
  useUpdateAsset,
} from './api'
import { UploadZone } from './UploadZone'

const kb = (n: number) =>
  n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`

/** The series' image library: upload, browse, edit metadata, see where each is used. */
export function LibraryView({
  seriesId,
  id,
  select,
}: {
  seriesId: string
  id: string | null
  select: (id: string | null) => void
}) {
  const assets = useAssets(seriesId)
  const [q, setQ] = useState('')
  const needle = q.trim().toLowerCase()
  const shown = (assets.data ?? []).filter(
    (a) =>
      !needle ||
      a.filename.toLowerCase().includes(needle) ||
      a.tags.some((t) => t.includes(needle)) ||
      a.alt_text.toLowerCase().includes(needle),
  )
  const current = assets.data?.find((a) => a.id === id)
  return (
    <div className="grid h-full gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-h-0 space-y-3 overflow-auto">
        <UploadZone
          seriesId={seriesId}
          onUploaded={(done) => done.length === 1 && select(done[0]!.id)}
        />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter by name, alt text or tag"
          aria-label="Filter images"
          className="w-full rounded-md border border-border bg-bg px-2.5 py-1.5 text-sm"
        />
        {assets.data?.length === 0 && (
          <EmptyState icon={ExternalLink} title="No images yet">
            Upload illustrations, covers and maps. Identical files are stored once.
          </EmptyState>
        )}
        <ul aria-label="Images" className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
          {shown.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                onClick={() => select(a.id === id ? null : a.id)}
                aria-current={a.id === id ? 'true' : undefined}
                aria-label={a.filename}
                className={cn(
                  'w-full overflow-hidden rounded-lg border bg-surface text-left',
                  a.id === id
                    ? 'border-accent ring-2 ring-accent/30'
                    : 'border-border hover:border-accent/60',
                )}
              >
                <img
                  src={a.thumb_url}
                  alt={a.alt_text}
                  loading="lazy"
                  className="aspect-[4/3] w-full bg-surface-2 object-cover"
                />
                <span className="block truncate px-2 pt-1.5 text-xs font-medium">{a.filename}</span>
                <span className="flex items-center gap-1 px-2 pb-1.5 text-[11px] text-muted">
                  {a.width_px}×{a.height_px} · {a.uses ? `used ${a.uses}×` : 'unused'}
                  {!a.alt_text && <span className="ml-auto text-warning">no alt text</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      {current ? (
        <AssetDetail
          key={current.id}
          asset={current}
          seriesId={seriesId}
          onDeleted={() => select(null)}
        />
      ) : (
        <p className="text-sm text-muted">Select an image to edit its details.</p>
      )}
    </div>
  )
}

function AssetDetail({
  asset: a,
  seriesId,
  onDeleted,
}: {
  asset: Asset
  seriesId: string
  onDeleted: () => void
}) {
  const update = useUpdateAsset(seriesId)
  const del = useDeleteAsset(seriesId)
  const uses = useAssetUses(a.id)
  const set = (
    patch: Parameters<typeof update.mutate>[0] extends infer T ? Omit<T, 'id'> : never,
  ) => update.mutate({ id: a.id, ...(patch as object) })
  return (
    <div className="min-h-0 space-y-4 overflow-auto">
      <Panel title="Image">
        <a href={a.url} target="_blank" rel="noreferrer">
          <img
            src={a.thumb_url}
            alt={a.alt_text}
            className="w-full rounded-lg bg-surface-2 object-contain"
          />
        </a>
        <p className="text-xs text-muted">
          {a.width_px} × {a.height_px} px · {kb(a.bytes)} ·{' '}
          {a.mime.replace('image/', '').toUpperCase()}. At 300 dpi it prints up to{' '}
          {Math.round((a.width_px / 300) * 25.4)} × {Math.round((a.height_px / 300) * 25.4)} mm.
        </p>
        <Field label="File name">
          {(id) => (
            <TextInput
              id={id}
              value={a.filename}
              onCommit={(filename) => filename && set({ filename })}
            />
          )}
        </Field>
        <Field label="Alt text" hint="Describes the image for screen readers and the EPUB.">
          {(id) => (
            <TextArea id={id} value={a.alt_text} onCommit={(alt_text) => set({ alt_text })} />
          )}
        </Field>
        <Field label="Caption">
          {(id) => <TextInput id={id} value={a.caption} onCommit={(caption) => set({ caption })} />}
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Credit">
            {(id) => <TextInput id={id} value={a.credit} onCommit={(credit) => set({ credit })} />}
          </Field>
          <Field label="Licence">
            {(id) => (
              <TextInput id={id} value={a.licence} onCommit={(licence) => set({ licence })} />
            )}
          </Field>
        </div>
        <Field label="Tags" hint="Comma-separated.">
          {(id) => (
            <TextInput
              id={id}
              value={a.tags.join(', ')}
              onCommit={(v) =>
                set({
                  tags: v
                    .split(',')
                    .map((t) => t.trim().toLowerCase())
                    .filter(Boolean),
                })
              }
            />
          )}
        </Field>
        {update.error && <p className="text-xs text-danger">{update.error.message}</p>}
      </Panel>
      <Panel title="Where it's used">
        {uses.data?.length === 0 && <p className="text-sm text-muted">Not used anywhere yet.</p>}
        <ul className="space-y-1 text-sm">
          {(uses.data ?? []).map((u) => (
            <li key={`${u.kind}:${u.id}`}>
              {u.node_id && u.book_id ? (
                <Link
                  to={`/story/${u.book_id}?node=${u.node_id}`}
                  className="text-accent hover:underline"
                >
                  {u.label}
                </Link>
              ) : (
                u.label || ROLE_LABELS[u.role]
              )}
              {u.book_title && <span className="text-muted"> · {u.book_title}</span>}
            </li>
          ))}
        </ul>
      </Panel>
      <Button
        variant="ghost"
        className="text-danger"
        onClick={() => {
          const n = uses.data?.length ?? 0
          if (
            n &&
            !window.confirm(
              `${a.filename} is used in ${n} place(s). Delete it anyway? They become placeholders.`,
            )
          )
            return
          del.mutate({ id: a.id, force: n > 0 }, { onSuccess: onDeleted })
        }}
      >
        <Trash2 className="size-4" /> Delete image
      </Button>
      {del.error && <p className="text-xs text-danger">{del.error.message}</p>}
    </div>
  )
}
