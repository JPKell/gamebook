import { createContext, useContext } from 'react'

import type { GbxContext, RuleSystemOut } from '@/api/types'

export interface VocabEntry {
  key: string
  label: string
  detail?: string
}

/** Names an author can use in gbx and effect editors, for one book. */
export interface Vocabulary {
  bookId: string
  seriesId: string
  tiers: VocabEntry[]
  stats: VocabEntry[]
  tests: VocabEntry[]
  skills: VocabEntry[]
  classes: VocabEntry[]
  items: VocabEntry[]
  flags: VocabEntry[]
  nodes: VocabEntry[]
}

export const EMPTY_VOCAB: Vocabulary = {
  bookId: '',
  seriesId: '',
  tiers: [],
  stats: [],
  tests: [],
  skills: [],
  classes: [],
  items: [],
  flags: [],
  nodes: [],
}

export const VocabularyContext = createContext<Vocabulary>(EMPTY_VOCAB)

export function useVocabulary(): Vocabulary {
  return useContext(VocabularyContext)
}

/** Flatten the active rule system's tiers into vocab lists (first tier that defines wins). */
export function rulesVocabulary(rules: RuleSystemOut | undefined) {
  const tiers: VocabEntry[] = []
  const stats = new Map<string, VocabEntry>()
  const tests = new Map<string, VocabEntry>()
  const skills = new Map<string, VocabEntry>()
  const classes = new Map<string, VocabEntry>()
  for (const t of rules?.definition.tiers ?? []) {
    tiers.push({ key: t.key, label: t.label })
    for (const s of t.stats ?? [])
      if (!stats.has(s.key)) stats.set(s.key, { key: s.key, label: s.label, detail: t.label })
    for (const s of t.tests ?? [])
      if (!tests.has(s.key)) tests.set(s.key, { key: s.key, label: s.label, detail: t.label })
    for (const s of t.skills ?? [])
      if (!skills.has(s.key)) skills.set(s.key, { key: s.key, label: s.label, detail: t.label })
    for (const s of t.classes ?? [])
      if (!classes.has(s.key)) classes.set(s.key, { key: s.key, label: s.label, detail: t.label })
  }
  return {
    tiers,
    stats: [...stats.values()],
    tests: [...tests.values()],
    skills: [...skills.values()],
    classes: [...classes.values()],
  }
}

export const CONTEXT_VARIABLES: Partial<Record<GbxContext, string[]>> = {
  test_success: ['roll'],
  enemy_formula: ['level'],
  combat_damage: ['damage', 'natural'],
}

export const FUNCTIONS: VocabEntry[] = [
  { key: 'has', label: 'has(item)', detail: 'you carry the item' },
  { key: 'count', label: 'count(item)', detail: 'how many you carry' },
  { key: 'equipped', label: 'equipped(item)', detail: 'item is equipped' },
  { key: 'flag', label: 'flag(CODEWORD)', detail: 'you have the codeword' },
  { key: 'skill', label: 'skill(SKILL)', detail: 'you have the skill' },
  { key: 'class', label: 'class(class)', detail: 'your class' },
  { key: 'visits', label: 'visits(node)', detail: 'times you have been there' },
  { key: 'min', label: 'min(a, b, …)' },
  { key: 'max', label: 'max(a, b, …)' },
  { key: 'floor', label: 'floor(x)', detail: 'round down' },
  { key: 'ceil', label: 'ceil(x)', detail: 'round up' },
  { key: 'round', label: 'round(x)', detail: 'halves round up' },
  { key: 'abs', label: 'abs(x)' },
  { key: 'clamp', label: 'clamp(x, lo, hi)' },
]
