import {
  Filter,
  LayoutGrid,
  Maximize,
  Plus,
  Redo2,
  Search,
  Settings2,
  Sparkles,
  Undo2,
  X,
} from 'lucide-react'
import type { RefObject } from 'react'

import { useHistoryState } from '@/api/queries'
import type { BookGraph } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/inputs'
import { Kbd } from '@/components/ui/kbd'
import { Menu } from '@/components/ui/menu'
import { cn, modKey } from '@/lib/utils'

import { anyFilter } from './model'
import { type StoryFilters, useStoryStore } from './storyStore'

const FILTER_LABELS: [keyof StoryFilters, string][] = [
  ['problems', 'Has problems'],
  ['gated', 'Has gated choices'],
  ['encounters', 'Has encounters'],
  ['items', 'Has items or a shop'],
  ['endings', 'Endings'],
]

export function CanvasToolbar({
  graph,
  searchRef,
  matchCount,
  onAddNode,
  onAutoLayout,
  onFit,
  onUndo,
  onRedo,
  onOpenBook,
  onSuggest,
  busy,
}: {
  graph: BookGraph
  searchRef: RefObject<HTMLInputElement | null>
  matchCount: number | null
  onAddNode: () => void
  onAutoLayout: () => void
  onFit: () => void
  onUndo: () => void
  onRedo: () => void
  onOpenBook: () => void
  onSuggest: () => void
  busy: boolean
}) {
  const { search, setSearch, filters, setFilters } = useStoryStore()
  const history = useHistoryState(graph.book.id)
  const filtering = anyFilter(filters)

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border bg-surface px-3 py-2">
      <div className="flex items-center gap-1">
        <Button size="sm" onClick={onAddNode} title="Add node (N)">
          <Plus className="size-4" /> Node
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onUndo}
          disabled={!history.data?.can_undo || busy}
          aria-label="Undo"
          title={
            history.data?.undo_label
              ? `Undo ${history.data.undo_label} (${modKey}+Z)`
              : 'Nothing to undo'
          }
        >
          <Undo2 className="size-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onRedo}
          disabled={!history.data?.can_redo || busy}
          aria-label="Redo"
          title={
            history.data?.redo_label
              ? `Redo ${history.data.redo_label} (${modKey}+Shift+Z)`
              : 'Nothing to redo'
          }
        >
          <Redo2 className="size-4" />
        </Button>
      </div>

      <div className="relative min-w-48 flex-1 sm:max-w-xs">
        <Search
          className="pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2 text-muted"
          aria-hidden
        />
        <input
          ref={searchRef}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setSearch('')
              e.currentTarget.blur()
            }
          }}
          placeholder="Search nodes…"
          aria-label="Search nodes"
          className="h-8 w-full rounded-md border border-border bg-bg pr-16 pl-8 text-sm focus:border-accent focus:outline-none"
        />
        <span className="absolute top-1/2 right-2 flex -translate-y-1/2 items-center gap-1 text-xs text-muted">
          {search ? (
            <>
              <span aria-live="polite">{matchCount ?? 0}</span>
              <button type="button" onClick={() => setSearch('')} aria-label="Clear search">
                <X className="size-3.5" />
              </button>
            </>
          ) : (
            <Kbd>{modKey} F</Kbd>
          )}
        </span>
      </div>

      <Menu
        align="start"
        trigger={
          <Button
            variant={filtering ? 'outline' : 'ghost'}
            size="sm"
            className={cn(filtering && 'border-accent text-accent')}
          >
            <Filter className="size-4" /> Filter
          </Button>
        }
      >
        <div className="space-y-1.5 p-2" onKeyDown={(e) => e.stopPropagation()}>
          <p className="pb-1 text-xs text-muted">Highlight nodes that…</p>
          {FILTER_LABELS.map(([k, label]) => (
            <div key={k}>
              <Checkbox
                checked={filters[k]}
                onCheckedChange={(v) => setFilters({ [k]: v })}
                label={label}
              />
            </div>
          ))}
        </div>
      </Menu>

      <div className="ml-auto flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={onAutoLayout}
          disabled={busy}
          title="Arrange each act automatically"
        >
          <LayoutGrid className="size-4" /> Auto-layout
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onFit}
          aria-label="Fit to screen"
          title="Fit to screen (F)"
        >
          <Maximize className="size-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onSuggest}
          title="Suggest sections for an act's outline"
        >
          <Sparkles className="size-4" /> Suggest
        </Button>
        <Button variant="ghost" size="sm" onClick={onOpenBook} title="Book details, style and acts">
          <Settings2 className="size-4" /> Book & acts
        </Button>
      </div>
    </div>
  )
}
