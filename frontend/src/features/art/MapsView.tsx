import { ImagePlus, MapPin, Plus, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { useBookGraph, useEntities } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty'
import { Field } from '@/components/ui/field'
import { Select, TextInput } from '@/components/ui/inputs'
import { Panel } from '@/features/entities/EntityHeader'
import { cn } from '@/lib/utils'

import { type ArtMap, type Marker, useCreateMap, useDeleteMap, useMaps, useUpdateMap } from './api'
import { AssetPicker } from './AssetPicker'

const newId = () => Math.random().toString(36).slice(2, 10)

/** Maps over library images, with markers linked to sections or lore locations. */
export function MapsView({
  seriesId,
  books,
  id,
  select,
}: {
  seriesId: string
  books: { id: string; title: string }[]
  id: string | null
  select: (id: string | null) => void
}) {
  const maps = useMaps(seriesId)
  const create = useCreateMap(seriesId)
  const current = maps.data?.find((m) => m.id === id) ?? maps.data?.[0]
  return (
    <div className="grid h-full gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
      <nav aria-label="Maps" className="space-y-2">
        <Button
          size="sm"
          onClick={() =>
            create.mutate(
              { title: `Map ${(maps.data?.length ?? 0) + 1}` },
              { onSuccess: (m) => select(m.id) },
            )
          }
        >
          <Plus className="size-4" /> New map
        </Button>
        <ul className="space-y-1">
          {(maps.data ?? []).map((m) => (
            <li key={m.id}>
              <button
                type="button"
                onClick={() => select(m.id)}
                aria-current={current?.id === m.id ? 'true' : undefined}
                className={cn(
                  'w-full truncate rounded-md px-2 py-1.5 text-left text-sm',
                  current?.id === m.id ? 'bg-accent/10 text-accent' : 'hover:bg-surface-2',
                )}
              >
                {m.title}
                <span className="block text-xs text-muted">
                  {m.markers.length} marker{m.markers.length === 1 ? '' : 's'}
                  {m.book_id
                    ? ` · ${books.find((b) => b.id === m.book_id)?.title ?? ''}`
                    : ' · whole series'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </nav>
      {current ? (
        <MapEditor
          key={current.id}
          map={current}
          seriesId={seriesId}
          books={books}
          onDeleted={() => select(null)}
        />
      ) : (
        <EmptyState icon={MapPin} title="No maps yet">
          A map is an image with markers that link to sections or places. Readers see it in the
          player, and it can be printed as an appendix.
        </EmptyState>
      )}
    </div>
  )
}

function MapEditor({
  map: m,
  seriesId,
  books,
  onDeleted,
}: {
  map: ArtMap
  seriesId: string
  books: { id: string; title: string }[]
  onDeleted: () => void
}) {
  const update = useUpdateMap(seriesId)
  const del = useDeleteMap(seriesId)
  const graph = useBookGraph(m.book_id ?? undefined)
  const lore = useEntities('lore', seriesId)
  const [picking, setPicking] = useState(false)
  // Edits build on a local copy: two quick edits (a label committed on blur, then a
  // link) must not each send the server's older list and undo one another.
  const server = m.markers as unknown as Marker[]
  const [markers, setMarkers] = useState<Marker[]>(server)
  // Handlers created before a re-render still read the newest list.
  const latest = useRef(markers)
  const [seen, setSeen] = useState(server)
  if (server !== seen && !update.isPending) {
    setSeen(server)
    setMarkers(server)
  }
  useEffect(() => {
    latest.current = markers
  }, [markers])
  const [selected, setSelected] = useState<string | null>(server[0]?.id ?? null)
  const save = (next: Marker[]) => {
    latest.current = next
    setMarkers(next)
    update.mutate(
      { id: m.id, markers: next },
      {
        // Refused (e.g. a bad condition): show what the server has again.
        onError: () => {
          latest.current = server
          setMarkers(server)
        },
      },
    )
  }
  const patch = (mid: string, p: Partial<Marker>) =>
    save(latest.current.map((x) => (x.id === mid ? { ...x, ...p } : x)))
  const sel = markers.find((x) => x.id === selected)
  const round = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 1000) / 1000
  return (
    <div className="min-h-0 space-y-4 overflow-auto">
      <Panel
        title="Map"
        aside={
          <Button
            size="sm"
            variant="ghost"
            className="text-danger"
            onClick={() =>
              window.confirm(`Delete ${m.title}?`) && del.mutate(m.id, { onSuccess: onDeleted })
            }
          >
            <Trash2 className="size-4" /> Delete map
          </Button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Title">
            {(id) => (
              <TextInput
                id={id}
                value={m.title}
                onCommit={(title) => title && update.mutate({ id: m.id, title })}
              />
            )}
          </Field>
          <Field label="Key">
            {(id) => (
              <TextInput
                id={id}
                value={m.key}
                onCommit={(key) => key && update.mutate({ id: m.id, key })}
              />
            )}
          </Field>
          <Field label="Book">
            {(id) => (
              <Select
                id={id}
                value={m.book_id}
                options={books.map((b) => ({ value: b.id, label: b.title }))}
                placeholder="Whole series"
                onValueChange={(book_id) => update.mutate({ id: m.id, book_id })}
              />
            )}
          </Field>
        </div>
        {update.error && <p className="text-xs text-danger">{update.error.message}</p>}
        <Button size="sm" variant="outline" onClick={() => setPicking(true)}>
          <ImagePlus className="size-4" /> {m.asset ? 'Change image' : 'Choose image'}
        </Button>
        <AssetPicker
          seriesId={seriesId}
          open={picking}
          onOpenChange={setPicking}
          onPick={(a) => update.mutate({ id: m.id, asset_id: a.id })}
        />
      </Panel>
      {m.asset && (
        <Panel title="Markers">
          <p className="text-xs text-muted">
            Click the map to add a marker. Select one and use the arrow keys to nudge it.
          </p>
          <div
            className="relative cursor-crosshair select-none"
            onClick={(e) => {
              if (e.target !== e.currentTarget.querySelector('img')) return
              const r = e.currentTarget.getBoundingClientRect()
              const mk: Marker = {
                id: newId(),
                x: round((e.clientX - r.left) / r.width),
                y: round((e.clientY - r.top) / r.height),
                label: `Marker ${markers.length + 1}`,
              }
              save([...latest.current, mk])
              setSelected(mk.id)
            }}
          >
            <img
              src={m.asset.url}
              alt={m.asset.alt_text || m.title}
              className="block w-full rounded-lg"
              draggable={false}
            />
            {markers.map((x, i) => (
              <button
                key={x.id}
                type="button"
                aria-label={`Marker ${i + 1}: ${x.label}`}
                aria-pressed={x.id === selected}
                onClick={() => setSelected(x.id)}
                onKeyDown={(e) => {
                  const step = e.shiftKey ? 0.05 : 0.01
                  const d: Record<string, [number, number]> = {
                    ArrowLeft: [-step, 0],
                    ArrowRight: [step, 0],
                    ArrowUp: [0, -step],
                    ArrowDown: [0, step],
                  }
                  const mv = d[e.key]
                  if (!mv) return
                  e.preventDefault()
                  patch(x.id, { x: round(x.x + mv[0]), y: round(x.y + mv[1]) })
                }}
                className={cn(
                  'absolute flex size-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white text-[11px] font-semibold text-white shadow',
                  x.id === selected ? 'bg-accent ring-2 ring-accent/40' : 'bg-black/70',
                )}
                style={{ left: `${x.x * 100}%`, top: `${x.y * 100}%` }}
              >
                {i + 1}
              </button>
            ))}
          </div>
          {sel && (
            <div
              key={sel.id}
              className="grid gap-3 rounded-lg border border-border p-3 sm:grid-cols-2"
            >
              <Field label="Label">
                {(id) => (
                  <TextInput
                    id={id}
                    value={sel.label ?? ''}
                    onCommit={(label) => patch(sel.id, { label })}
                  />
                )}
              </Field>
              {m.book_id ? (
                <Field label="Links to section">
                  {(id) => (
                    <Select
                      id={id}
                      value={sel.node_id ?? null}
                      placeholder="None"
                      options={(graph.data?.nodes ?? []).map((n) => ({
                        value: n.id,
                        label: n.title,
                      }))}
                      onValueChange={(node_id) => patch(sel.id, { node_id })}
                    />
                  )}
                </Field>
              ) : (
                <span />
              )}
              <Field label="Links to place">
                {(id) => (
                  <Select
                    id={id}
                    value={sel.lore_id ?? null}
                    placeholder="None"
                    options={(lore.data ?? []).map((l) => ({ value: l.id, label: l.name }))}
                    onValueChange={(lore_id) => patch(sel.id, { lore_id })}
                  />
                )}
              </Field>
              <Field
                label="Only shown if"
                hint="A condition, e.g. flag(found_map). Empty: always shown."
              >
                {(id) => (
                  <TextInput
                    id={id}
                    value={sel.visible_if ?? ''}
                    className="font-mono"
                    onCommit={(v) => patch(sel.id, { visible_if: v.trim() || null })}
                  />
                )}
              </Field>
              <div className="sm:col-span-2">
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-danger"
                  onClick={() => {
                    save(latest.current.filter((x) => x.id !== sel.id))
                    setSelected(null)
                  }}
                >
                  <Trash2 className="size-4" /> Remove marker
                </Button>
              </div>
            </div>
          )}
        </Panel>
      )}
    </div>
  )
}
