/** The game bundle's book, as `core/engine/bundle.py` writes it (format "gamebook-bundle"). */

export interface Effect {
  op: 'modify' | 'set' | 'give' | 'take' | 'equip' | 'set_flag' | 'clear_flag' | 'learn'
  once?: boolean | null
  min_tier?: string | null
  print_text?: string | null
  stat?: string
  amount?: string
  value?: string
  item?: string
  qty?: number
  flag?: string
  skill?: string
}

export interface Outcome {
  id: string
  key: string
  target_id: string | null
  range_lo?: number | null
  range_hi?: number | null
}

export interface Choice {
  id: string
  node_id: string
  label: string
  kind: 'goto' | 'roll' | 'test' | 'combat'
  unmet_display: string
  condition: string | null
  min_tier: string | null
  effects: Effect[]
  dice: string | null
  test: string | null
  encounter_id: string | null
  flee_allowed: boolean
  outcomes: Outcome[]
}

export interface Variant {
  id: string
  label: string
  condition: string | null
  priority: number
}

export interface Encounter {
  id: string
  label: string
  mode: 'fixed' | 'table'
  fight: 'sequential' | 'simultaneous'
  table_id: string | null
  enemies: { enemy_id: string; level: number; count: number }[]
}

export interface Node {
  id: string
  key: string
  title: string
  act_id: string
  shop_sell_rate: number | null
  is_act_entry: boolean
  is_act_exit: boolean
  ending_kind: string | null
  ending_grade: string | null
  on_enter: Effect[]
  variants: Variant[]
  choices: Choice[]
  encounters: Encounter[]
  items: { item_id: string; qty: number }[]
  shop: { item_id: string; price: number; stock: number | null }[] | null
}

export interface Entity {
  id: string
  key: string
  name: string
  book_id: string | null
}

export interface Item extends Entity {
  category: string
  slot: string | null
  value: number
  max_stack: number | null
  modifiers: { stat: string; amount: string; min_tier: string | null }[]
  use_effects: Effect[]
}

export interface Enemy extends Entity {
  stat_formulas: Record<string, string>
  default_level: number
}

export interface TableEntry {
  lo: number
  hi: number
  kind: 'enemies' | 'item' | 'gold' | 'nothing'
  enemies: [string, number, number][]
  item: string | null
  qty: number
  amount: string | null
}

export interface RandomTable extends Entity {
  dice: string
  entries: TableEntry[]
}

export interface StatDef {
  key: string
  label: string
  description: string
  kind: 'stat' | 'resource'
  applies_to: ('player' | 'enemy')[]
  initial: string
  min: number | null
  max: number | null
  max_is_initial: boolean
  defeat_at: number | null
}

export interface TestDef {
  key: string
  label: string
  description: string
  roll: string
  success: string
  after: Effect[]
}

export interface CombatDef {
  player_attack: string | null
  enemy_attack: string | null
  damage: string | null
  damage_stat: string | null
  damage_hooks: string[]
  multi_enemy: 'sequential' | 'simultaneous' | null
  flee_allowed: boolean | null
  flee_cost: Effect[] | null
}

export interface StatBonus {
  stat: string
  amount: string
}

export interface StartingItem {
  item: string
  qty: number
  equip: boolean
}

export interface ClassDef {
  key: string
  label: string
  description: string
  skills: string[]
  /** Missing in bundles from before levelling (treated as empty). */
  modifiers?: StatBonus[]
  starting_items?: StartingItem[]
}

export interface ProgressionDef {
  xp_stat: string | null
  level_stat: string | null
  xp_award: string | null
  xp_to_next: string | null
  max_level: number | null
  level_up: StatBonus[] | null
}

export interface TierDef {
  key: string
  label: string
  parent: string | null
  description: string
  stats: StatDef[]
  tests: TestDef[]
  skills: { key: string; label: string; description: string }[]
  classes: ClassDef[]
  slots: string[]
  combat: CombatDef
  progression?: Partial<ProgressionDef>
  starting_items?: StartingItem[]
  rules_text: string
}

export interface Book {
  book_id: string
  series_id: string
  title: string
  start_node_id: string | null
  acts: { id: string; key: string; title: string; position: number }[]
  nodes: Node[]
  rules: { tiers: TierDef[] } | null
  items: Item[]
  enemies: Enemy[]
  tables: RandomTable[]
  characters: Entity[]
  lore: Entity[]
}

export interface GameBundle {
  format: 'gamebook-bundle'
  version: number
  book: Book
}

export const BUNDLE_VERSION = 1

export function readBundle(raw: unknown): Book {
  const b = raw as Partial<GameBundle>
  if (b?.format !== 'gamebook-bundle') throw new Error('Not a game bundle')
  if (Number(b.version ?? 0) > BUNDLE_VERSION) throw new Error('Bundle is from a newer version')
  return b.book as Book
}

/** Entities are usable when shared by the series or belonging to this book. */
export const available = (book: Book, e: Entity) =>
  e.book_id === null || e.book_id === undefined || e.book_id === book.book_id
