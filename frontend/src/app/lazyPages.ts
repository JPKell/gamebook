import { lazy } from 'react'

// Feature pages load on demand so the shell starts fast.
export const LibraryPage = lazy(() =>
  import('@/features/library/LibraryPage').then((m) => ({ default: m.LibraryPage })),
)
export const StoryIndex = lazy(() =>
  import('@/features/story/StoryPage').then((m) => ({ default: m.StoryIndex })),
)
export const StoryPage = lazy(() =>
  import('@/features/story/StoryPage').then((m) => ({ default: m.StoryPage })),
)
export const MechanicsIndex = lazy(() =>
  import('@/features/mechanics/MechanicsPage').then((m) => ({ default: m.MechanicsIndex })),
)
export const MechanicsPage = lazy(() =>
  import('@/features/mechanics/MechanicsPage').then((m) => ({ default: m.MechanicsPage })),
)
export const EnemiesIndex = lazy(() =>
  import('@/features/entities/pages').then((m) => ({ default: m.EnemiesIndex })),
)
export const EnemiesPage = lazy(() =>
  import('@/features/entities/pages').then((m) => ({ default: m.EnemiesPage })),
)
export const ItemsIndex = lazy(() =>
  import('@/features/entities/pages').then((m) => ({ default: m.ItemsIndex })),
)
export const ItemsPage = lazy(() =>
  import('@/features/entities/pages').then((m) => ({ default: m.ItemsPage })),
)
export const PlaytestIndex = lazy(() =>
  import('@/features/playtest/PlaytestPage').then((m) => ({ default: m.PlaytestIndex })),
)
export const PlaytestPage = lazy(() =>
  import('@/features/playtest/PlaytestPage').then((m) => ({ default: m.PlaytestPage })),
)
export const ArtIndex = lazy(() =>
  import('@/features/art/ArtPage').then((m) => ({ default: m.ArtIndex })),
)
export const ArtPage = lazy(() =>
  import('@/features/art/ArtPage').then((m) => ({ default: m.ArtPage })),
)
export const LoreIndex = lazy(() =>
  import('@/features/lore/LorePage').then((m) => ({ default: m.LoreIndex })),
)
export const LorePage = lazy(() =>
  import('@/features/lore/LorePage').then((m) => ({ default: m.LorePage })),
)
export const WritingIndex = lazy(() =>
  import('@/features/writing/WritingPage').then((m) => ({ default: m.WritingIndex })),
)
export const WritingPage = lazy(() =>
  import('@/features/writing/WritingPage').then((m) => ({ default: m.WritingPage })),
)
export const SettingsPage = lazy(() =>
  import('@/features/llm/SettingsPage').then((m) => ({ default: m.SettingsPage })),
)
