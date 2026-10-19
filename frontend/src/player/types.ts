/** What `book.js` provides (`window.GAMEBOOK`, format "gamebook-player"; see services/web_player.py). */
import type { GameBundle } from '@/engine/model'

export interface PlayerArt {
  file: string
  alt: string
  caption: string
  display: 'full_width' | 'inline' | 'thumbnail'
  zoom: boolean
  variant_id: string | null
  tier: string | null
}

export interface PlayerMarker {
  id: string
  x: number
  y: number
  label?: string
  node_id?: string
  visible_if?: string
}

export interface PlayerBook {
  format: 'gamebook-player'
  version: number
  book_id: string
  title: string
  series_title: string
  tiers: { key: string; label: string }[]
  bundle: GameBundle
  text: Record<string, string>
  notes: Record<string, string>
  art: Record<string, PlayerArt[]>
  cover: { file: string; alt: string } | null
  maps: { id: string; title: string; file: string | null; alt: string; markers: PlayerMarker[] }[]
  codex: Record<string, { id: string; title: string; kind: string; html: string }[]>
}

export const PLAYER_VERSION = 1

declare global {
  interface Window {
    GAMEBOOK?: PlayerBook
  }
}

export function checkBook(raw: unknown): PlayerBook {
  const b = raw as Partial<PlayerBook>
  if (b?.format !== 'gamebook-player') throw new Error('This is not a gamebook web player file.')
  if ((b.version ?? 0) > PLAYER_VERSION) throw new Error('This book needs a newer player.')
  return b as PlayerBook
}
