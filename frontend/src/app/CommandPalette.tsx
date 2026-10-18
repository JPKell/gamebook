import { Command } from 'cmdk'
import { CircleDot, Layers, Monitor, Moon, PanelBottom, Sun } from 'lucide-react'
import { type ReactNode, useEffect } from 'react'
import { useNavigate } from 'react-router'

import { useBookGraph } from '@/api/queries'
import { useStoryStore } from '@/features/story/storyStore'
import { isModShortcut } from '@/lib/utils'
import { TIERS, useUiStore } from '@/stores/ui'

import { SECTIONS } from './sections'
import { useCurrentBookId } from './useCurrentBook'

/** Ctrl/Cmd+K command palette. New features register commands here as they land. */
export function CommandPalette() {
  const navigate = useNavigate()
  const { paletteOpen, setPaletteOpen, setTheme, setTier, toggleProblems } = useUiStore()
  const bookId = useCurrentBookId()
  const graph = useBookGraph(bookId)
  const { openNode, reveal } = useStoryStore()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isModShortcut(e, 'k')) {
        e.preventDefault()
        setPaletteOpen(!useUiStore.getState().paletteOpen)
      } else if (isModShortcut(e, 'j')) {
        e.preventDefault()
        toggleProblems()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setPaletteOpen, toggleProblems])

  const run = (action: () => void) => () => {
    setPaletteOpen(false)
    action()
  }

  return (
    <Command.Dialog
      open={paletteOpen}
      onOpenChange={setPaletteOpen}
      label="Command palette"
      overlayClassName="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]"
      contentClassName="fixed left-1/2 top-[15vh] z-50 w-[min(560px,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
    >
      <Command.Input
        placeholder="Type a command or search…"
        className="h-12 w-full border-b border-border bg-transparent px-4 outline-none placeholder:text-muted"
      />
      <Command.List className="max-h-80 overflow-auto p-2">
        <Command.Empty className="px-3 py-6 text-center text-muted">No results.</Command.Empty>
        {graph.data && (
          <Group heading={`Nodes in ${graph.data.book.title}`}>
            {graph.data.nodes.map((n) => (
              <Item
                key={n.id}
                value={`node ${n.title} ${n.key}`}
                onSelect={run(() => {
                  openNode(n.id)
                  reveal(n.id)
                })}
                icon={<CircleDot />}
              >
                {n.title}
                <span className="ml-auto font-mono text-xs text-muted">{n.key}</span>
              </Item>
            ))}
          </Group>
        )}
        <Group heading="Go to">
          {SECTIONS.map((s) => (
            <Item key={s.id} onSelect={run(() => navigate(s.path))} icon={<s.icon />}>
              {s.label}
            </Item>
          ))}
        </Group>
        <Group heading="Rules tier">
          {TIERS.map((t) => (
            <Item
              key={t.id}
              value={`tier ${t.label}`}
              onSelect={run(() => setTier(t.id))}
              icon={<Layers />}
            >
              Play as {t.label}
            </Item>
          ))}
        </Group>
        <Group heading="View">
          <Item onSelect={run(toggleProblems)} icon={<PanelBottom />}>
            Toggle problems panel
          </Item>
          <Item onSelect={run(() => setTheme('light'))} icon={<Sun />}>
            Theme: Light
          </Item>
          <Item onSelect={run(() => setTheme('dark'))} icon={<Moon />}>
            Theme: Dark
          </Item>
          <Item onSelect={run(() => setTheme('system'))} icon={<Monitor />}>
            Theme: System
          </Item>
        </Group>
      </Command.List>
    </Command.Dialog>
  )
}

function Group({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <Command.Group
      heading={heading}
      className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted"
    >
      {children}
    </Command.Group>
  )
}

function Item({
  children,
  icon,
  onSelect,
  value,
}: {
  children: ReactNode
  icon: ReactNode
  onSelect: () => void
  value?: string
}) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-2 text-text data-[selected=true]:bg-accent/12 [&_svg]:size-4 [&_svg]:text-muted"
    >
      {icon}
      {children}
    </Command.Item>
  )
}
