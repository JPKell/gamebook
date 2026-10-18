import { create } from 'zustand'

export type InspectorTab = 'beat' | 'choices' | 'encounters' | 'variants' | 'lore'

export interface StoryFilters {
  problems: boolean
  gated: boolean
  encounters: boolean
  items: boolean
  endings: boolean
}

export const NO_FILTERS: StoryFilters = {
  problems: false,
  gated: false,
  encounters: false,
  items: false,
  endings: false,
}

interface StoryState {
  selectedIds: string[]
  /** Choice to highlight/expand in the inspector (e.g. after clicking an edge). */
  focusChoiceId: string | null
  /** Node to bring into view on the canvas (consumed by the canvas). */
  revealId: string | null
  tab: InspectorTab
  search: string
  filters: StoryFilters
  clipboard: string[]
  select: (ids: string[]) => void
  openNode: (id: string, tab?: InspectorTab, choiceId?: string | null) => void
  reveal: (id: string | null) => void
  setTab: (tab: InspectorTab) => void
  setSearch: (q: string) => void
  setFilters: (f: Partial<StoryFilters>) => void
  copy: (ids: string[]) => void
  reset: () => void
}

export const useStoryStore = create<StoryState>()((set) => ({
  selectedIds: [],
  focusChoiceId: null,
  revealId: null,
  tab: 'beat',
  search: '',
  filters: NO_FILTERS,
  clipboard: [],
  select: (selectedIds) =>
    set((s) => (sameIds(s.selectedIds, selectedIds) ? s : { selectedIds, focusChoiceId: null })),
  openNode: (id, tab, choiceId = null) =>
    set((s) => ({ selectedIds: [id], tab: tab ?? s.tab, focusChoiceId: choiceId })),
  reveal: (revealId) => set({ revealId }),
  setTab: (tab) => set({ tab }),
  setSearch: (search) => set({ search }),
  setFilters: (f) => set((s) => ({ filters: { ...s.filters, ...f } })),
  copy: (clipboard) => set({ clipboard }),
  reset: () =>
    set({ selectedIds: [], focusChoiceId: null, revealId: null, search: '', filters: NO_FILTERS }),
}))

function sameIds(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((x, i) => x === b[i])
}
