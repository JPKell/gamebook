import type { StateStorage } from 'zustand/middleware'

/** localStorage that degrades to a no-op when unavailable (private mode, blocked). */
export const safeLocalStorage: StateStorage = {
  getItem: (name) => {
    try {
      return window.localStorage.getItem(name)
    } catch {
      return null
    }
  },
  setItem: (name, value) => {
    try {
      window.localStorage.setItem(name, value)
    } catch {
      // ignore: preferences just won't persist
    }
  },
  removeItem: (name) => {
    try {
      window.localStorage.removeItem(name)
    } catch {
      // ignore
    }
  },
}
