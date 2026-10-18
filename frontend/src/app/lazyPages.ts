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
