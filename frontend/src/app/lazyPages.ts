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
