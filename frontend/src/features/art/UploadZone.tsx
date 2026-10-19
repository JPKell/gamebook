import { ImageUp } from 'lucide-react'
import { useId, useState } from 'react'

import { cn } from '@/lib/utils'

import { type Asset, useUploadAssets } from './api'

export const ACCEPT = 'image/png,image/jpeg,image/webp'

/** Drop images here or browse; reports per-file failures. */
export function UploadZone({
  seriesId,
  onUploaded,
  compact = false,
}: {
  seriesId: string
  onUploaded?: (assets: Asset[]) => void
  compact?: boolean
}) {
  const id = useId()
  const upload = useUploadAssets(seriesId)
  const [over, setOver] = useState(false)
  const send = (list: FileList | null) => {
    const files = [...(list ?? [])]
    if (files.length) upload.mutate(files, { onSuccess: (r) => onUploaded?.(r.done) })
  }
  const result = upload.data
  return (
    <div className="space-y-1">
      <label
        htmlFor={id}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          send(e.dataTransfer.files)
        }}
        className={cn(
          'flex cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border text-sm text-muted transition-colors hover:border-accent hover:text-text',
          compact ? 'px-3 py-2' : 'px-4 py-6',
          over && 'border-accent bg-accent/5 text-text',
        )}
      >
        <ImageUp className="size-4" aria-hidden />
        {upload.isPending ? 'Uploading…' : 'Drop PNG, JPEG or WebP images here, or browse'}
        <input
          id={id}
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          aria-label="Upload images"
          onChange={(e) => {
            send(e.target.files)
            e.target.value = ''
          }}
        />
      </label>
      {result && !upload.isPending && (
        <p role="status" className="text-xs text-muted">
          {result.done.length > 0 &&
            `Added ${result.done.filter((a) => a.created).length} image(s)${
              result.done.some((a) => !a.created) ? ' (duplicates reused)' : ''
            }. `}
          {result.failed.map((f) => (
            <span key={f.name} className="block text-danger">
              {f.name}: {f.error}
            </span>
          ))}
        </p>
      )}
    </div>
  )
}
