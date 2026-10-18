import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

import { safeLocalStorage } from '@/lib/storage'

export type ThemePref = 'light' | 'dark' | 'system'
export type Tier = 'basic' | 'medium' | 'advanced'

export const TIERS: { id: Tier; label: string }[] = [
  { id: 'basic', label: 'Basic' },
  { id: 'medium', label: 'Medium' },
  { id: 'advanced', label: 'Advanced' },
]

interface UiState {
  theme: ThemePref
  tier: Tier
  problemsOpen: boolean
  paletteOpen: boolean
  /** Last book opened in the Story view (restored on next visit). */
  lastBookId: string | null
  setTheme: (theme: ThemePref) => void
  setTier: (tier: Tier) => void
  setProblemsOpen: (open: boolean) => void
  toggleProblems: () => void
  setPaletteOpen: (open: boolean) => void
  setLastBookId: (id: string | null) => void
}

/** UI-only state. Server data lives in TanStack Query, never here. */
export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      theme: 'system',
      tier: 'basic',
      problemsOpen: false,
      paletteOpen: false,
      lastBookId: null,
      setTheme: (theme) => set({ theme }),
      setTier: (tier) => set({ tier }),
      setProblemsOpen: (problemsOpen) => set({ problemsOpen }),
      toggleProblems: () => set((s) => ({ problemsOpen: !s.problemsOpen })),
      setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
      setLastBookId: (lastBookId) => set({ lastBookId }),
    }),
    {
      name: 'gamebook-ui',
      version: 1,
      storage: createJSONStorage(() => safeLocalStorage),
      partialize: ({ theme, tier, problemsOpen, lastBookId }) => ({
        theme,
        tier,
        problemsOpen,
        lastBookId,
      }),
    },
  ),
)
