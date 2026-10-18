import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

export const isMac =
  typeof navigator !== 'undefined' &&
  /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)

/** Label for the platform's primary modifier key. */
export const modKey = isMac ? '⌘' : 'Ctrl'

/** True for Ctrl+<key> (or Cmd+<key> on macOS) without other modifiers. */
export function isModShortcut(e: KeyboardEvent, key: string): boolean {
  const mod = isMac ? e.metaKey : e.ctrlKey
  return mod && !e.altKey && !e.shiftKey && e.key.toLowerCase() === key
}
