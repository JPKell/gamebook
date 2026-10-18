import { useEffect } from 'react'

import { isMac } from '@/lib/utils'

export interface StoryShortcutHandlers {
  undo: () => void
  redo: () => void
  copy: () => void
  paste: () => void
  duplicate: () => void
  newNode: () => void
  fit: () => void
  focusSearch: () => void
  deselect: () => void
}

/** True while typing in a field — leave text editing keys to the browser. */
export function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return (
    target.isContentEditable ||
    ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) ||
    !!target.closest('.cm-editor')
  )
}

export function useStoryShortcuts(h: StoryShortcutHandlers) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = isMac ? e.metaKey : e.ctrlKey
      const key = e.key.toLowerCase()
      if (mod && key === 'f' && !e.shiftKey) {
        e.preventDefault()
        h.focusSearch()
        return
      }
      if (isTyping(e.target) || e.altKey) return
      if (mod && key === 'z') {
        e.preventDefault()
        if (e.shiftKey) h.redo()
        else h.undo()
      } else if (mod && key === 'y') {
        e.preventDefault()
        h.redo()
      } else if (mod && key === 'c') {
        h.copy()
      } else if (mod && key === 'v') {
        e.preventDefault()
        h.paste()
      } else if (mod && key === 'd') {
        e.preventDefault()
        h.duplicate()
      } else if (!mod && !e.shiftKey && key === 'n') {
        e.preventDefault()
        h.newNode()
      } else if (!mod && !e.shiftKey && key === 'f') {
        h.fit()
      } else if (key === 'escape') {
        h.deselect()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [h])
}
