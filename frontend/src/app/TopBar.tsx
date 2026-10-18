import { ChevronRight, Monitor, Moon, Search, Sun } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Kbd } from '@/components/ui/kbd'
import { cn, modKey } from '@/lib/utils'
import { TIERS, type ThemePref, useUiStore } from '@/stores/ui'

const THEME_CYCLE: Record<ThemePref, { next: ThemePref; icon: typeof Sun; label: string }> = {
  system: { next: 'light', icon: Monitor, label: 'System theme' },
  light: { next: 'dark', icon: Sun, label: 'Light theme' },
  dark: { next: 'system', icon: Moon, label: 'Dark theme' },
}

export function TopBar() {
  const { theme, setTheme, tier, setTier, setPaletteOpen } = useUiStore()
  const themeInfo = THEME_CYCLE[theme]

  return (
    <header className="flex h-12 items-center gap-3 border-b border-border bg-surface px-3">
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1 text-muted">
        <span className="font-semibold text-text">Gamebook Studio</span>
        <ChevronRight className="size-4 shrink-0" aria-hidden />
        <span title="Series and book switching arrives in Phase 2" className="truncate italic">
          No series open
        </span>
      </nav>

      <button
        type="button"
        onClick={() => setPaletteOpen(true)}
        className="mx-auto flex h-8 w-full max-w-sm items-center gap-2 rounded-md border border-border bg-bg px-2.5 text-muted transition-colors hover:border-accent/50"
      >
        <Search className="size-4" aria-hidden />
        <span className="flex-1 text-left">Search or run a command…</span>
        <Kbd>{modKey} K</Kbd>
      </button>

      <div
        role="radiogroup"
        aria-label="Rules tier"
        className="flex rounded-md border border-border bg-bg p-0.5"
      >
        {TIERS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="radio"
            aria-checked={tier === t.id}
            onClick={() => setTier(t.id)}
            className={cn(
              'rounded px-2.5 py-1 text-xs font-medium text-muted transition-colors',
              tier === t.id ? 'bg-accent text-accent-fg' : 'hover:text-text',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <Button
        variant="ghost"
        size="icon"
        onClick={() => setTheme(themeInfo.next)}
        aria-label={`${themeInfo.label} (click to change)`}
        title={themeInfo.label}
      >
        <themeInfo.icon className="size-4" aria-hidden />
      </Button>
    </header>
  )
}
