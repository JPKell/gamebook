import {
  BookOpen,
  Dices,
  FileOutput,
  FlaskConical,
  Gem,
  type LucideIcon,
  PenLine,
  Settings,
  Skull,
  Workflow,
} from 'lucide-react'

export interface Section {
  id: string
  label: string
  path: string
  icon: LucideIcon
  /** Build phase (docs/PLAN.md) in which this section becomes functional. */
  phase: number
  summary: string
  upcoming: string[]
}

/** Single source of truth for top-level navigation, routes and palette commands. */
export const SECTIONS: Section[] = [
  {
    id: 'story',
    label: 'Story',
    path: '/story',
    icon: Workflow,
    phase: 2,
    summary: 'The book as a graph: acts, nodes and choices.',
    upcoming: [
      'Whole-book canvas with acts as group frames',
      'Drag-to-link choices, auto-layout, minimap',
      'Inspector panel for beats, choices, effects and prose',
    ],
  },
  {
    id: 'lore',
    label: 'Lore',
    path: '/lore',
    icon: BookOpen,
    phase: 6,
    summary: 'Characters, places, factions, act outlines and story beats.',
    upcoming: ['Wiki with [[mentions]] and backlinks', 'Act outlines linked to nodes'],
  },
  {
    id: 'enemies',
    label: 'Enemies',
    path: '/enemies',
    icon: Skull,
    phase: 4,
    summary: 'Every enemy, its per-level stat formulas and where it appears.',
    upcoming: ['Per-tier stat formulas with live level tables', 'Where-used across all books'],
  },
  {
    id: 'items',
    label: 'Items',
    path: '/items',
    icon: Gem,
    phase: 4,
    summary: 'Equipment, consumables, key items and shops.',
    upcoming: ['Auto-computed quantities from placements', 'Modifiers per tier'],
  },
  {
    id: 'mechanics',
    label: 'Mechanics',
    path: '/mechanics',
    icon: Dices,
    phase: 3,
    summary: 'Layered Basic → Medium → Advanced rule tiers.',
    upcoming: ['Stats, tests and combat procedure per tier', 'Combat lab with Monte Carlo sims'],
  },
  {
    id: 'writing',
    label: 'Writing',
    path: '/writing',
    icon: PenLine,
    phase: 7,
    summary: 'LLM prose drafting with writer, critic and editor passes.',
    upcoming: ['Review queue with diffs and critique trail', 'Stale-prose tracking'],
  },
  {
    id: 'playtest',
    label: 'Playtest',
    path: '/playtest',
    icon: FlaskConical,
    phase: 5,
    summary: 'Play the book yourself, or run bots and LLM players at scale.',
    upcoming: ['Win/death rates per tier and act', 'Coverage and heat-map overlays'],
  },
  {
    id: 'export',
    label: 'Export',
    path: '/export',
    icon: FileOutput,
    phase: 10,
    summary: 'Git tree, print/PDF, EPUB and the digital player bundle.',
    upcoming: ['Seeded, pinnable section numbering', 'Per-tier print editions'],
  },
  {
    id: 'settings',
    label: 'Settings',
    path: '/settings',
    icon: Settings,
    phase: 7,
    summary: 'LLM providers, prompt templates and app preferences.',
    upcoming: ['Provider profiles (local, OpenAI, OpenRouter)', 'Prompt template editor'],
  },
]
