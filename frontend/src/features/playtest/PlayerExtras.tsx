import { BookMarked, Map as MapIcon } from 'lucide-react'
import { useState } from 'react'

import type { components } from '@/api/schema'
import { Select } from '@/components/ui/inputs'
import { useCodex } from '@/features/art/api'
import { cn } from '@/lib/utils'

type PlayOut = components['schemas']['PlayOut']

/** The section's artwork, as its digital layout asks (full width, inline or thumbnail). */
export function SceneArt({ art }: { art: PlayOut['art'] }) {
  const [zoomed, setZoomed] = useState<string | null>(null)
  if (!art?.length) return null
  return (
    <div className="space-y-3">
      {art.map((a) => {
        const img = (
          <img
            src={a.display === 'thumbnail' ? a.thumb_url : a.url}
            alt={a.alt}
            className={cn(
              'rounded-lg bg-surface-2',
              a.display === 'full_width' && 'w-full',
              a.display === 'inline' && 'mx-auto max-h-80 max-w-full',
              a.display === 'thumbnail' && 'size-24 object-cover',
            )}
          />
        )
        return (
          <figure key={a.url} className={a.display === 'thumbnail' ? 'float-right ml-3' : ''}>
            {a.zoom ? (
              <button
                type="button"
                onClick={() => setZoomed(a.url)}
                aria-label={`Enlarge: ${a.alt || 'illustration'}`}
              >
                {img}
              </button>
            ) : (
              img
            )}
            {a.caption && (
              <figcaption className="mt-1 text-center text-xs text-muted">{a.caption}</figcaption>
            )}
          </figure>
        )
      })}
      {zoomed && (
        <button
          type="button"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6"
          onClick={() => setZoomed(null)}
          aria-label="Close the enlarged image"
        >
          <img src={zoomed} alt="" className="max-h-full max-w-full rounded-lg" />
        </button>
      )}
    </div>
  )
}

/** The book's maps; markers appear once their condition holds (e.g. a codeword). */
export function MapPanel({ maps }: { maps: PlayOut['maps'] }) {
  const [index, setIndex] = useState(0)
  const list = maps ?? []
  if (!list.length) return null
  const m = list[Math.min(index, list.length - 1)]!
  return (
    <section aria-label="Map" className="space-y-2 rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center gap-2">
        <MapIcon className="size-4 text-muted" aria-hidden />
        <h3 className="text-sm font-semibold">{m.title}</h3>
        {list.length > 1 && (
          <Select
            aria-label="Choose a map"
            value={String(index)}
            options={list.map((x, i) => ({ value: String(i), label: x.title }))}
            onValueChange={(v) => setIndex(Number(v ?? 0))}
            className="ml-auto w-auto"
          />
        )}
      </div>
      {m.url ? (
        <div className="relative">
          <img src={m.url} alt={m.alt} className="block w-full rounded-lg" />
          {m.markers.map((mk) => (
            <span
              key={mk.id}
              title={mk.label}
              className={cn(
                'absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow',
                mk.here ? 'size-4 bg-accent ring-4 ring-accent/30' : 'bg-black/70',
              )}
              style={{ left: `${mk.x * 100}%`, top: `${mk.y * 100}%` }}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted">No image yet.</p>
      )}
      <ul className="space-y-0.5 text-xs" aria-label={`Places on ${m.title}`}>
        {m.markers.map((mk) => (
          <li key={mk.id} className={mk.here ? 'font-semibold text-accent' : 'text-muted'}>
            {mk.label}
            {mk.here && ' (you are here)'}
          </li>
        ))}
      </ul>
    </section>
  )
}

/** The book's appendices as a codex; the bestiary and items fill in as the reader meets them. */
export function CodexPanel({ bookId, view }: { bookId: string; view: PlayOut }) {
  const [open, setOpen] = useState(false)
  const [pick, setPick] = useState<string | null>(null)
  const codex = useCodex(
    bookId,
    open && view.codex?.available
      ? { tier: view.tier, enemies: view.codex.enemies ?? [], items: view.codex.items ?? [] }
      : null,
  )
  if (!view.codex?.available) return null
  const entries = codex.data ?? []
  const current = entries.find((e) => e.id === pick) ?? entries[0]
  return (
    <section
      aria-label="Codex"
      className="space-y-2 rounded-xl border border-border bg-surface p-4"
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 text-sm font-semibold"
      >
        <BookMarked className="size-4 text-muted" aria-hidden /> Codex
      </button>
      {open && (
        <>
          {entries.length > 1 && (
            <Select
              aria-label="Codex page"
              value={current?.id ?? null}
              options={entries.map((e) => ({ value: e.id, label: e.title }))}
              onValueChange={setPick}
            />
          )}
          {current ? (
            <iframe
              title={current.title}
              srcDoc={current.document}
              sandbox=""
              className="h-96 w-full rounded-lg border border-border bg-white"
            />
          ) : (
            <p className="text-sm text-muted">
              {codex.isFetching ? 'Loading…' : 'Nothing here yet.'}
            </p>
          )}
        </>
      )}
    </section>
  )
}
