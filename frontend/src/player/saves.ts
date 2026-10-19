/**
 * Save slots in localStorage. A save is the game's inputs, not its state: replaying
 * them through the engine restores the game exactly (dice included).
 */
export interface Move {
  type: string
  target: string | null
}

export interface Session {
  tier: string
  seed: number
  characterClass: string | null
  moves: Move[]
}

export interface Slot extends Session {
  id: string
  name: string
  savedAt: string
  /** Where the reader was, for the slot list. */
  where: string
}

export const AUTOSAVE = 'autosave'

const key = (bookId: string) => `gamebook:${bookId}:slots`

/** A slot that can be replayed (anything else in storage is ignored, not trusted). */
function isSlot(s: unknown): s is Slot {
  const x = s as Slot
  return (
    !!x &&
    typeof x.id === 'string' &&
    typeof x.tier === 'string' &&
    Number.isSafeInteger(x.seed) &&
    x.seed >= 0 &&
    Array.isArray(x.moves) &&
    x.moves.every((m) => m && typeof m.type === 'string')
  )
}

export function loadSlots(bookId: string): Slot[] {
  try {
    const raw = localStorage.getItem(key(bookId))
    const slots: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(slots) ? slots.filter(isSlot) : []
  } catch {
    return [] // private mode, blocked storage or a damaged entry: start fresh
  }
}

function store(bookId: string, slots: Slot[]): boolean {
  try {
    localStorage.setItem(key(bookId), JSON.stringify(slots))
    return true
  } catch {
    return false
  }
}

export function saveSlot(bookId: string, slot: Slot): boolean {
  const others = loadSlots(bookId).filter((s) => s.id !== slot.id)
  return store(bookId, [slot, ...others].slice(0, 20))
}

export function deleteSlot(bookId: string, id: string): void {
  store(
    bookId,
    loadSlots(bookId).filter((s) => s.id !== id),
  )
}

export const newSeed = () => 1 + Math.floor(Math.random() * 2_000_000_000)
