import type { BookGraph, NodeOut } from '@/api/types'
import { DEFAULT_SETUP, useBookPlacements, usePageSetup } from '@/features/art/api'
import { PlacementList } from '@/features/art/PlacementEditor'
import { useSeriesVocab } from '@/features/entities/useSeriesVocab'

/** Illustrations for a section: images or placeholders, with print and digital layout. */
export function ArtTab({ graph, node }: { graph: BookGraph; node: NodeOut }) {
  const bookId = graph.book.id
  const seriesId = graph.book.series_id
  const placements = useBookPlacements(bookId)
  const setup = usePageSetup(bookId)
  const vocab = useSeriesVocab(seriesId)
  const mine = (placements.data ?? []).filter((p) => p.node_id === node.id)
  if (placements.isPending) return <p className="text-sm text-muted">Loading…</p>
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        Illustrations print with this section and show in the player. A placeholder with a brief
        holds the space until the art arrives.
      </p>
      <PlacementList
        label={`Artwork for ${node.title}`}
        seriesId={seriesId}
        targetType="node"
        targetId={node.id}
        roles={['illustration']}
        placements={mine}
        setup={setup.data ?? DEFAULT_SETUP}
        variants={node.variants.map((v) => ({ id: v.id, label: v.label }))}
        tiers={vocab.tiers}
      />
    </div>
  )
}
