import { useEffect, useState } from 'react'

import { useUiStore } from '@/stores/ui'

const DARK_QUERY = '(prefers-color-scheme: dark)'

/** Applies the theme preference to <html>, following the OS when set to "system". */
export function useApplyTheme(): void {
  const theme = useUiStore((s) => s.theme)

  useEffect(() => {
    const media = window.matchMedia?.(DARK_QUERY)
    const apply = () => {
      const dark = theme === 'dark' || (theme === 'system' && (media?.matches ?? false))
      document.documentElement.classList.toggle('dark', dark)
    }
    apply()
    if (theme !== 'system' || !media) return
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [theme])
}

/** The effective light/dark theme (follows the OS when set to "system"). */
export function useResolvedTheme(): 'light' | 'dark' {
  const theme = useUiStore((s) => s.theme)
  const [systemDark, setSystemDark] = useState(
    () => window.matchMedia?.(DARK_QUERY).matches ?? false,
  )
  useEffect(() => {
    const media = window.matchMedia?.(DARK_QUERY)
    if (!media) return
    const onChange = () => setSystemDark(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])
  return theme === 'system' ? (systemDark ? 'dark' : 'light') : theme
}
