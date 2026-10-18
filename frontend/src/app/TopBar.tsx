import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  History,
  Library,
  Monitor,
  Moon,
  Search,
  Sun,
} from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import { useBook, useSeries } from '@/api/queries'
import { Menu, MenuItem, MenuSeparator } from '@/components/ui/menu'

import { Button } from '@/components/ui/button'
import { Kbd } from '@/components/ui/kbd'
import { cn, modKey } from '@/lib/utils'
import { TIERS, type ThemePref, useUiStore } from '@/stores/ui'

import { CheckpointsDialog } from './CheckpointsDialog'
import { useCurrentBookId } from './useCurrentBook'

const THEME_CYCLE: Record<ThemePref, { next: ThemePref; icon: typeof Sun; label: string }> = {
  system: { next: 'light', icon: Monitor, label: 'System theme' },
  light: { next: 'dark', icon: Sun, label: 'Light theme' },
  dark: { next: 'system', icon: Moon, label: 'Dark theme' },
}

export function TopBar() {
  const { theme, setTheme, tier, setTier, setPaletteOpen } = useUiStore()
  const themeInfo = THEME_CYCLE[theme]
  const [checkpoints, setCheckpoints] = useState(false)

  return (
    <header className="flex h-12 items-center gap-3 border-b border-border bg-surface px-3">
      <Breadcrumb />

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
        onClick={() => setCheckpoints(true)}
        aria-label="Checkpoints"
        title="Checkpoints (whole-library snapshots)"
      >
        <History className="size-4" aria-hidden />
      </Button>
      <CheckpointsDialog open={checkpoints} onOpenChange={setCheckpoints} />
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

function Breadcrumb() {
  const bookId = useCurrentBookId()
  const book = useBook(bookId)
  const series = useSeries(book.data?.series_id)
  const navigate = useNavigate()
  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1 text-muted">
      <span className="font-semibold whitespace-nowrap text-text">Gamebook Studio</span>
      {series.data && book.data && (
        <>
          <ChevronRight className="size-4 shrink-0" aria-hidden />
          <span className="truncate">{series.data.title}</span>
          <ChevronRight className="size-4 shrink-0" aria-hidden />
          <Menu
            align="start"
            trigger={
              <button
                type="button"
                className="flex min-w-0 items-center gap-1 rounded px-1 font-medium text-text hover:bg-surface-2"
                aria-label={`Book: ${book.data.title}. Switch book`}
              >
                <span className="truncate">{book.data.title}</span>
                <ChevronDown className="size-3.5 shrink-0" aria-hidden />
              </button>
            }
          >
            {series.data.books.map((b) => (
              <MenuItem
                key={b.id}
                icon={<BookOpen />}
                disabled={b.id === bookId}
                onSelect={() => navigate(`/story/${b.id}`)}
              >
                {b.number ? `${b.number}. ` : ''}
                {b.title}
              </MenuItem>
            ))}
            <MenuSeparator />
            <MenuItem icon={<Library />} onSelect={() => navigate('/library')}>
              Library
            </MenuItem>
          </Menu>
        </>
      )}
    </nav>
  )
}
