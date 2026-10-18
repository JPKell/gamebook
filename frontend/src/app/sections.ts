import {
  BookOpen,
  Dices,
  FileOutput,
  FlaskConical,
  Gem,
  Image,
  Library,
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
  /** Built sections render their own page instead of the placeholder. */
  summary: string
  upcoming: string[]
}

/** Single source of truth for top-level navigation, routes and palette commands. */
export const SECTIONS: Section[] = [
  {
    id: 'library',
    label: 'Library',
    path: '/library',
    icon: Library,
    phase: 2,
    summary: 'Your series and books.',
    upcoming: [],
  },
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
    upcoming: [],
  },
  {
    id: 'enemies',
    label: 'Enemies',
    path: '/enemies',
    icon: Skull,
    phase: 4,
    summary: 'Every enemy, its per-level stat formulas and where it appears.',
    upcoming: [],
  },
  {
    id: 'items',
    label: 'Items',
    path: '/items',
    icon: Gem,
    phase: 4,
    summary: 'Equipment, consumables, key items and shops.',
    upcoming: [],
  },
  {
    id: 'art',
    label: 'Art',
    path: '/art',
    icon: Image,
    phase: 10,
    summary: 'Illustrations, full-page art, maps and appendices.',
    upcoming: [
      'Image library with alt text, credits and where-used',
      'Node illustrations with print size, position, wrap and DPI checks',
      'Act openers, covers and maps with clickable markers',
      'Generated appendices: bestiary, adventure sheet, item catalogue, rules reference',
      'Commissioning tracker and shot list for illustrators',
    ],
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
    upcoming: [],
  },
  {
    id: 'playtest',
    label: 'Playtest',
    path: '/playtest',
    icon: FlaskConical,
    phase: 5,
    summary: 'Play the book yourself, or run bots and LLM players at scale.',
    upcoming: [],
  },
  {
    id: 'export',
    label: 'Export',
    path: '/export',
    icon: FileOutput,
    phase: 11,
    summary: 'Git tree, print/PDF, EPUB and the digital player bundle.',
    upcoming: [
      'Seeded, pinnable section numbering',
      'Per-tier print editions',
      'Artwork laid out to your print sizes, appendices as back matter',
    ],
  },
  {
    id: 'settings',
    label: 'Settings',
    path: '/settings',
    icon: Settings,
    phase: 7,
    summary: 'LLM providers, prompt templates and app preferences.',
    upcoming: [],
  },
]
