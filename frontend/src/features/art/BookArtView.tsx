import { Link } from 'react-router'

import { useBookGraph } from '@/api/queries'
import { Field } from '@/components/ui/field'
import { NumberInput } from '@/components/ui/inputs'
import { Panel } from '@/features/entities/EntityHeader'
import { useSeriesVocab } from '@/features/entities/useSeriesVocab'

import { DEFAULT_SETUP, setupBody, useBookPlacements, usePageSetup, useSavePageSetup } from './api'
import { PagePreview } from './PagePreview'
import { PlacementList } from './PlacementEditor'

const BOOK_ROLES = ['cover_front', 'cover_back', 'frontispiece', 'title_page', 'endpaper']
type SetupNumber =
  | 'trim_width_mm'
  | 'trim_height_mm'
  | 'margin_inner_mm'
  | 'margin_outer_mm'
  | 'margin_top_mm'
  | 'margin_bottom_mm'
  | 'gutter_mm'
  | 'bleed_mm'
const SETUP_FIELDS: { key: SetupNumber; label: string }[] = [
  { key: 'trim_width_mm', label: 'Trim width' },
  { key: 'trim_height_mm', label: 'Trim height' },
  { key: 'margin_inner_mm', label: 'Inner margin' },
  { key: 'margin_outer_mm', label: 'Outer margin' },
  { key: 'margin_top_mm', label: 'Top margin' },
  { key: 'margin_bottom_mm', label: 'Bottom margin' },
  { key: 'gutter_mm', label: 'Gutter' },
  { key: 'bleed_mm', label: 'Bleed' },
]

/** Page setup, covers and front matter, and act openers for one book. */
export function BookArtView({ seriesId, bookId }: { seriesId: string; bookId: string }) {
  const graph = useBookGraph(bookId)
  const setup = usePageSetup(bookId)
  const save = useSavePageSetup(bookId)
  const placements = useBookPlacements(bookId)
  const vocab = useSeriesVocab(seriesId)
  const page = setup.data ?? DEFAULT_SETUP
  const all = placements.data ?? []
  const common = { seriesId, setup: page, tiers: vocab.tiers }
  const acts = [...(graph.data?.acts ?? [])].sort((a, b) => a.position - b.position)
  return (
    <div className="grid h-full gap-4 overflow-auto lg:grid-cols-[320px_minmax(0,1fr)]">
      <div className="space-y-4">
        <Panel title="Page setup">
          <p className="text-xs text-muted">
            Millimetres. Print sizes and DPI checks follow from these. Dashed red: bleed; dashed
            blue: the text block (safe area).
          </p>
          <PagePreview setup={page} className="mx-auto w-40" />
          <div className="grid grid-cols-2 gap-3">
            {SETUP_FIELDS.map(({ key, label }) => (
              <Field key={key} label={label}>
                {(id) => (
                  <NumberInput
                    id={id}
                    disabled={!!page.imposition?.fold && key.startsWith('trim')}
                    min={0}
                    step={0.5}
                    value={page[key]}
                    onCommit={(v) => {
                      if (v === null) return
                      save.mutate({ ...setupBody(page), [key]: v })
                    }}
                  />
                )}
              </Field>
            ))}
          </div>
          <p className="text-xs text-muted">
            Text block {page.text_width} × {page.text_height} mm.
          </p>
          <Link to={`/export/${bookId}/layout`} className="text-sm text-accent hover:underline">
            Fonts, text styles, headers and signatures…
          </Link>
          {save.error && <p className="text-xs text-danger">{save.error.message}</p>}
        </Panel>
      </div>
      <div className="space-y-4">
        <Panel title="Covers and front matter">
          <PlacementList
            label="Book art"
            targetType="book"
            targetId={bookId}
            roles={BOOK_ROLES}
            placements={all.filter((p) => p.target_type === 'book')}
            {...common}
          />
        </Panel>
        <Panel title="Act openers">
          <p className="text-xs text-muted">
            Full-page art at the start of each act (right-hand page by default).
          </p>
          {acts.map((act) => (
            <div key={act.id} className="space-y-2">
              <h3 className="text-sm font-semibold">{act.title}</h3>
              <PlacementList
                label={`Opener for ${act.title}`}
                targetType="act"
                targetId={act.id}
                roles={['opener']}
                placements={all.filter((p) => p.act_id === act.id && p.target_type === 'act')}
                {...common}
              />
            </div>
          ))}
        </Panel>
      </div>
    </div>
  )
}
