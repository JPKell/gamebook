import { Panel } from '@/features/entities/EntityHeader'

import { DEFAULT_SETUP, type TargetType, useTargetPlacements } from './api'
import { PlacementList } from './PlacementEditor'

/** Portraits and images for a character, enemy, item or lore entry (used by the
 * lore pages, appendices and the player's codex). */
export function EntityArt({
  seriesId,
  targetType,
  targetId,
  name,
}: {
  seriesId: string
  targetType: Extract<TargetType, 'character' | 'enemy' | 'item' | 'lore'>
  targetId: string
  name: string
}) {
  const placements = useTargetPlacements(targetType, targetId)
  return (
    <Panel title="Portrait">
      <PlacementList
        label={`Images of ${name}`}
        seriesId={seriesId}
        targetType={targetType}
        targetId={targetId}
        roles={['portrait', 'image']}
        placements={placements.data ?? []}
        setup={DEFAULT_SETUP}
      />
    </Panel>
  )
}
