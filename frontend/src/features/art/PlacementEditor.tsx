import { ArrowDown, ArrowUp, ImageOff, ImagePlus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Checkbox, NumberInput, Select, TextArea, TextInput } from '@/components/ui/inputs'
import { cn } from '@/lib/utils'

import {
  type PageSetup,
  type Placement,
  type PrintLayout,
  ROLE_LABELS,
  STATUS_LABELS,
  type TargetType,
  useCreatePlacement,
  useDeletePlacement,
  useReorderPlacements,
  useUpdatePlacement,
} from './api'
import { AssetPicker } from './AssetPicker'
import { DpiBadge } from './DpiBadge'
import { PagePreview } from './PagePreview'
import { useLatest } from './useLatest'

const SIZES: { value: PrintLayout['size']; label: string }[] = [
  { value: 'full_page', label: 'Full page' },
  { value: 'full_width', label: 'Full width' },
  { value: 'half', label: 'Half width' },
  { value: 'third', label: 'Third width' },
  { value: 'vignette', label: 'Vignette (~30 mm)' },
  { value: 'custom', label: 'Custom' },
]
const POSITIONS: { value: PrintLayout['position']; label: string }[] = [
  { value: 'before_text', label: 'Before the text' },
  { value: 'after_text', label: 'After the text' },
  { value: 'after_paragraph', label: 'After paragraph…' },
  { value: 'own_page', label: 'Its own page' },
  { value: 'facing_page', label: 'Facing page' },
]
const ASPECTS: { value: PrintLayout['aspect']; label: string }[] = [
  { value: 'original', label: 'Original' },
  { value: '1:1', label: '1:1' },
  { value: '4:3', label: '4:3' },
  { value: '3:2', label: '3:2' },
  { value: '2:3', label: '2:3 (portrait)' },
  { value: '16:9', label: '16:9' },
]
const WRAPPABLE = new Set(['half', 'third', 'vignette', 'custom'])

interface Common {
  seriesId: string
  setup: PageSetup
  variants?: { id: string; label: string }[]
  tiers?: { key: string; label: string }[]
}

/** Every placement on one target, with add / reorder / edit / remove. */
export function PlacementList({
  targetType,
  targetId,
  placements,
  roles,
  label,
  ...common
}: Common & {
  targetType: TargetType
  targetId: string
  placements: Placement[]
  roles: string[]
  /** Accessible name of the list, e.g. "Artwork for Hall". */
  label: string
}) {
  const create = useCreatePlacement(common.seriesId)
  const reorder = useReorderPlacements(common.seriesId)
  const [picking, setPicking] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const ids = placements.map((p) => p.id)
  const move = (i: number, d: number) => {
    const next = [...ids]
    ;[next[i], next[i + d]] = [next[i + d]!, next[i]!]
    reorder.mutate(next)
  }
  const add = (asset_id: string | null) =>
    create.mutate(
      {
        target_type: targetType,
        target_id: targetId,
        role: roles[0] as Placement['role'] as never,
        asset_id,
      },
      { onSuccess: (p) => setOpen(p.id) },
    )
  return (
    <section aria-label={label} className="space-y-3">
      <ul className="space-y-2">
        {placements.map((p, i) => (
          <li key={p.id} className="rounded-lg border border-border">
            <div className="flex items-center gap-2 p-2">
              <button
                type="button"
                onClick={() => setOpen(open === p.id ? null : p.id)}
                aria-expanded={open === p.id}
                className="flex min-w-0 flex-1 items-center gap-2 text-left"
              >
                {p.asset ? (
                  <img
                    src={p.asset.thumb_url}
                    alt=""
                    className="size-10 shrink-0 rounded bg-surface-2 object-cover"
                  />
                ) : (
                  <span className="flex size-10 shrink-0 items-center justify-center rounded border border-dashed border-border text-muted">
                    <ImageOff className="size-4" aria-hidden />
                  </span>
                )}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">
                    {ROLE_LABELS[p.role]}
                    {p.asset
                      ? `: ${p.asset.filename}`
                      : p.brief
                        ? `: ${p.brief}`
                        : ' (placeholder)'}
                  </span>
                  <span className="flex items-center gap-1.5 text-xs text-muted">
                    <DpiBadge size={p.print_size} />
                    {STATUS_LABELS[p.status]}
                  </span>
                </span>
              </button>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Move ${ROLE_LABELS[p.role]} ${i + 1} up`}
                disabled={i === 0}
                onClick={() => move(i, -1)}
              >
                <ArrowUp className="size-4" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Move ${ROLE_LABELS[p.role]} ${i + 1} down`}
                disabled={i === placements.length - 1}
                onClick={() => move(i, 1)}
              >
                <ArrowDown className="size-4" />
              </Button>
            </div>
            {open === p.id && (
              <div className="border-t border-border p-3">
                <PlacementEditor placement={p} roles={roles} {...common} />
              </div>
            )}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => setPicking(true)} disabled={create.isPending}>
          <ImagePlus className="size-4" /> Add image
        </Button>
        <Button size="sm" variant="outline" onClick={() => add(null)} disabled={create.isPending}>
          Add placeholder
        </Button>
      </div>
      {create.error && <p className="text-xs text-danger">{create.error.message}</p>}
      <AssetPicker
        seriesId={common.seriesId}
        open={picking}
        onOpenChange={setPicking}
        onPick={(a) => add(a.id)}
      />
    </section>
  )
}

/** Brief, status, media, variant/tier limits, print layout (with DPI and page preview), digital. */
export function PlacementEditor({
  placement: p,
  roles,
  seriesId,
  setup,
  variants,
  tiers,
}: Common & { placement: Placement; roles: string[] }) {
  const update = useUpdatePlacement(seriesId)
  const del = useDeletePlacement(seriesId)
  const [picking, setPicking] = useState(false)
  const set = (
    patch: Parameters<typeof update.mutate>[0] extends infer T ? Omit<T, 'id'> : never,
  ) => update.mutate({ id: p.id, ...(patch as object) })
  const mergeLayout = useLatest(p.layout, update.isPending)
  const mergeDigital = useLatest(p.digital, update.isPending)
  const lay = (patch: Partial<PrintLayout>) => set({ layout: mergeLayout(patch) })
  const L = p.layout
  const printed = p.media !== 'digital'
  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" onClick={() => setPicking(true)}>
          <ImagePlus className="size-4" /> {p.asset ? 'Change image' : 'Choose image'}
        </Button>
        {p.asset && (
          <Button size="sm" variant="ghost" onClick={() => set({ asset_id: null })}>
            Make placeholder
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          className="ml-auto text-danger"
          onClick={() => del.mutate(p.id)}
          aria-label={`Remove ${ROLE_LABELS[p.role]}`}
        >
          <Trash2 className="size-4" /> Remove
        </Button>
      </div>
      <AssetPicker
        seriesId={seriesId}
        open={picking}
        onOpenChange={setPicking}
        onPick={(a) => set({ asset_id: a.id })}
      />
      {update.error && <p className="text-xs text-danger">{update.error.message}</p>}

      <div className="grid grid-cols-2 gap-3">
        {roles.length > 1 && (
          <Field label="Role">
            {(id) => (
              <Select
                id={id}
                value={p.role}
                options={roles.map((r) => ({ value: r, label: ROLE_LABELS[r] ?? r }))}
                onValueChange={(r) => r && set({ role: r as never })}
              />
            )}
          </Field>
        )}
        <Field label="Status">
          {(id) => (
            <Select
              id={id}
              value={p.status}
              options={Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }))}
              onValueChange={(s) => s && set({ status: s as Placement['status'] as never })}
            />
          )}
        </Field>
        <Field label="Used in">
          {(id) => (
            <Select
              id={id}
              value={p.media}
              options={[
                { value: 'both', label: 'Print and digital' },
                { value: 'print', label: 'Print only' },
                { value: 'digital', label: 'Digital only' },
              ]}
              onValueChange={(m) => m && set({ media: m as never })}
            />
          )}
        </Field>
        {variants && variants.length > 1 && (
          <Field label="Text variant">
            {(id) => (
              <Select
                id={id}
                value={p.variant_id}
                placeholder="All variants"
                options={variants.map((v) => ({ value: v.id, label: v.label }))}
                onValueChange={(v) => set({ variant_id: v })}
              />
            )}
          </Field>
        )}
        {tiers && tiers.length > 1 && (
          <Field label="Tier">
            {(id) => (
              <Select
                id={id}
                value={p.tier}
                placeholder="Every tier"
                options={tiers.map((t) => ({ value: t.key, label: t.label }))}
                onValueChange={(t) => set({ tier: t })}
              />
            )}
          </Field>
        )}
      </div>
      <Field label="Caption">
        {(id) => <TextInput id={id} value={p.caption} onCommit={(caption) => set({ caption })} />}
      </Field>
      <Field label="Brief for the illustrator" hint="What to draw; appears in the shot list.">
        {(id) => <TextArea id={id} value={p.brief} onCommit={(brief) => set({ brief })} />}
      </Field>

      {printed && (
        <fieldset className="space-y-3 rounded-lg border border-border p-3">
          <legend className="flex items-center gap-2 px-1 text-xs font-semibold">
            Print layout <DpiBadge size={p.print_size} />
          </legend>
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_140px]">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Size">
                {(id) => (
                  <Select
                    id={id}
                    value={L.size}
                    options={SIZES}
                    onValueChange={(size) => size && lay({ size })}
                  />
                )}
              </Field>
              {L.size === 'full_page' ? (
                <div className="pt-5">
                  <Checkbox
                    label="Bleed off the edges"
                    checked={L.bleed}
                    onCheckedChange={(bleed) => lay({ bleed })}
                  />
                </div>
              ) : (
                <Field label="Align">
                  {(id) => (
                    <Select
                      id={id}
                      value={L.align}
                      options={[
                        { value: 'left', label: 'Left' },
                        { value: 'center', label: 'Centre' },
                        { value: 'right', label: 'Right' },
                      ]}
                      onValueChange={(align) => align && lay({ align })}
                    />
                  )}
                </Field>
              )}
              {L.size === 'custom' && (
                <>
                  <Field label="Width (mm)">
                    {(id) => (
                      <NumberInput
                        id={id}
                        allowEmpty
                        min={1}
                        value={L.width_mm ?? null}
                        onCommit={(v) => lay({ width_mm: v, width_pct: v ? null : L.width_pct })}
                      />
                    )}
                  </Field>
                  <Field label="or width (% of text)">
                    {(id) => (
                      <NumberInput
                        id={id}
                        allowEmpty
                        min={1}
                        max={100}
                        value={L.width_pct ?? null}
                        onCommit={(v) => lay({ width_pct: v, width_mm: v ? null : L.width_mm })}
                      />
                    )}
                  </Field>
                </>
              )}
              <Field label="Max height (mm)">
                {(id) => (
                  <NumberInput
                    id={id}
                    allowEmpty
                    min={1}
                    value={L.max_height_mm ?? null}
                    onCommit={(v) => lay({ max_height_mm: v })}
                  />
                )}
              </Field>
              <Field label="Crop">
                {(id) => (
                  <Select
                    id={id}
                    value={L.aspect}
                    options={ASPECTS}
                    onValueChange={(aspect) => aspect && lay({ aspect })}
                  />
                )}
              </Field>
              <Field label="Position">
                {(id) => (
                  <Select
                    id={id}
                    value={L.position}
                    options={POSITIONS}
                    onValueChange={(position) => position && lay({ position })}
                  />
                )}
              </Field>
              {L.position === 'after_paragraph' ? (
                <Field label="Paragraph">
                  {(id) => (
                    <NumberInput
                      id={id}
                      min={1}
                      value={L.paragraph}
                      onCommit={(v) => v && lay({ paragraph: v })}
                    />
                  )}
                </Field>
              ) : L.position === 'own_page' ? (
                <Field label="Page">
                  {(id) => (
                    <Select
                      id={id}
                      value={L.page_side}
                      options={[
                        { value: 'any', label: 'Either side' },
                        { value: 'recto', label: 'Right-hand (recto)' },
                        { value: 'verso', label: 'Left-hand (verso)' },
                      ]}
                      onValueChange={(page_side) => page_side && lay({ page_side })}
                    />
                  )}
                </Field>
              ) : (
                <span />
              )}
              {WRAPPABLE.has(L.size) && L.align !== 'center' && (
                <>
                  <div className="pt-1">
                    <Checkbox
                      label="Wrap text around it"
                      checked={L.wrap}
                      onCheckedChange={(wrap) => lay({ wrap })}
                    />
                  </div>
                  {L.wrap && (
                    <Field label="Gutter (mm)">
                      {(id) => (
                        <NumberInput
                          id={id}
                          min={0}
                          max={30}
                          value={L.gutter_mm}
                          onCommit={(v) => v !== null && lay({ gutter_mm: v })}
                        />
                      )}
                    </Field>
                  )}
                </>
              )}
              <div className="col-span-2">
                <Checkbox
                  label="Keep on the same spread as its section"
                  checked={L.keep_with}
                  onCheckedChange={(keep_with) => lay({ keep_with })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <PagePreview
                setup={setup}
                placement={p}
                imageUrl={p.asset?.thumb_url}
                className="w-full"
              />
              <p className="text-[11px] text-muted">
                Prints at {p.print_size.width_mm} × {p.print_size.height_mm} mm. 300 dpi needs{' '}
                {p.print_size.needed_px[0]} × {p.print_size.needed_px[1]} px.
              </p>
            </div>
          </div>
          {p.asset && L.aspect !== 'original' && (
            <FocalPoint
              src={p.asset.thumb_url}
              x={L.focal_x}
              y={L.focal_y}
              onChange={(focal_x, focal_y) => lay({ focal_x, focal_y })}
            />
          )}
        </fieldset>
      )}

      {p.media !== 'print' && (
        <fieldset className="grid grid-cols-2 gap-3 rounded-lg border border-border p-3">
          <legend className="px-1 text-xs font-semibold">Digital player</legend>
          <Field label="Display">
            {(id) => (
              <Select
                id={id}
                value={p.digital.display}
                options={[
                  { value: 'full_width', label: 'Full width' },
                  { value: 'inline', label: 'Inline' },
                  { value: 'thumbnail', label: 'Thumbnail' },
                ]}
                onValueChange={(display) => display && set({ digital: mergeDigital({ display }) })}
              />
            )}
          </Field>
          <div className="pt-5">
            <Checkbox
              label="Tap to enlarge"
              checked={p.digital.zoom}
              onCheckedChange={(zoom) => set({ digital: mergeDigital({ zoom }) })}
            />
          </div>
        </fieldset>
      )}
    </div>
  )
}

/** Click (or arrow keys) to set the crop's focal point. */
function FocalPoint({
  src,
  x,
  y,
  onChange,
}: {
  src: string
  x: number
  y: number
  onChange: (x: number, y: number) => void
}) {
  const clamp = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 100) / 100
  return (
    <div className="space-y-1">
      <p className="text-xs text-muted">
        Focal point (kept in the crop): click the image or use the arrow keys.
      </p>
      <div
        role="slider"
        tabIndex={0}
        aria-label="Crop focal point"
        aria-valuetext={`${Math.round(x * 100)}% across, ${Math.round(y * 100)}% down`}
        aria-valuenow={Math.round(x * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        onKeyDown={(e) => {
          const step = e.shiftKey ? 0.1 : 0.02
          const moves: Record<string, [number, number]> = {
            ArrowLeft: [-step, 0],
            ArrowRight: [step, 0],
            ArrowUp: [0, -step],
            ArrowDown: [0, step],
          }
          const m = moves[e.key]
          if (m) {
            e.preventDefault()
            onChange(clamp(x + m[0]), clamp(y + m[1]))
          }
        }}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect()
          onChange(clamp((e.clientX - r.left) / r.width), clamp((e.clientY - r.top) / r.height))
        }}
        className="relative inline-block max-w-56 cursor-crosshair focus-visible:outline-2 focus-visible:outline-accent"
      >
        <img src={src} alt="" className="block w-full rounded" draggable={false} />
        <span
          className={cn(
            'pointer-events-none absolute size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow ring-2 ring-accent',
          )}
          style={{ left: `${x * 100}%`, top: `${y * 100}%` }}
        />
      </div>
    </div>
  )
}
