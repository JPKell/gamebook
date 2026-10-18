import { Outlet } from 'react-router'
import { Toaster } from 'sonner'

import { CommandPalette } from './CommandPalette'
import { NavRail } from './NavRail'
import { StatusBar } from './StatusBar'
import { TopBar } from './TopBar'
import { useApplyTheme, useResolvedTheme } from './useTheme'

export function AppShell() {
  useApplyTheme()
  const theme = useResolvedTheme()
  return (
    <div className="grid h-dvh grid-cols-[auto_1fr] grid-rows-[auto_1fr_auto]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <NavRail />
      <TopBar />
      <main id="main" tabIndex={-1} className="min-h-0 overflow-auto outline-none">
        <Outlet />
      </main>
      <StatusBar />
      <CommandPalette />
      <Toaster theme={theme} position="bottom-right" offset={44} closeButton />
    </div>
  )
}
