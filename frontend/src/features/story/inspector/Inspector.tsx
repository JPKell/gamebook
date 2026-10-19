import { Copy, Flag, MoreHorizontal, MousePointerClick, Trash2, X } from 'lucide-react'

import { useDeleteNodes, useDuplicateNodes, useUpdateBook, useUpdateNode } from '@/api/mutations'
import type { BookGraph, NodeOut } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Select, TextInput } from '@/components/ui/inputs'
import { Kbd } from '@/components/ui/kbd'
import { Menu, MenuItem, MenuSeparator } from '@/components/ui/menu'
import { Tabs } from '@/components/ui/tabs'
import { modKey } from '@/lib/utils'

import { sortedActs } from '../model'
import { type InspectorTab, useStoryStore } from '../storyStore'
import { ArtTab } from './ArtTab'
import { BeatTab } from './BeatTab'
import { ChoicesTab } from './ChoicesTab'
import { EncountersTab } from './EncountersTab'
import { DigestTab } from './DigestTab'
import { LoreTab } from './LoreTab'
import { VariantsTab } from './VariantsTab'

export function Inspector({ graph }: { graph: BookGraph }) {
  const selectedIds = useStoryStore((s) => s.selectedIds)
  const nodes = selectedIds
    .map((id) => graph.nodes.find((n) => n.id === id))
    .filter((n): n is NodeOut => !!n)

  if (nodes.length === 0) return <InspectorEmpty />
  if (nodes.length > 1) return <MultiSelection graph={graph} nodes={nodes} />
  return <NodeInspector key={nodes[0]!.id} graph={graph} node={nodes[0]!} />
}

function InspectorEmpty() {
  const tips: [string, string][] = [
    ['Double-click', 'empty canvas to add a node'],
    ['Drag', 'from a node’s right handle to link it — drop on empty space to create a new node'],
    ['N', 'adds a node · F fits the view'],
    [`${modKey}+Z`, 'undoes any change, even after a reload'],
    [`${modKey}+C / V / D`, 'copy, paste, duplicate'],
  ]
  return (
    <div className="p-5 text-sm">
      <div className="mb-4 flex items-center gap-2 text-muted">
        <MousePointerClick className="size-5" aria-hidden /> Select a node to edit it.
      </div>
      <ul className="space-y-2 text-xs text-muted">
        {tips.map(([k, t]) => (
          <li key={k}>
            <Kbd>{k}</Kbd> {t}
          </li>
        ))}
      </ul>
    </div>
  )
}

function MultiSelection({ graph, nodes }: { graph: BookGraph; nodes: NodeOut[] }) {
  const bookId = graph.book.id
  const del = useDeleteNodes(bookId)
  const dup = useDuplicateNodes(bookId)
  const update = useUpdateNode(bookId)
  const select = useStoryStore((s) => s.select)
  return (
    <div className="space-y-4 p-5">
      <h2 className="font-semibold">{nodes.length} nodes selected</h2>
      <ul className="max-h-48 space-y-1 overflow-auto text-sm text-muted">
        {nodes.map((n) => (
          <li key={n.id} className="truncate">
            {n.title}
          </li>
        ))}
      </ul>
      <Select
        aria-label="Move selected nodes to act"
        value={null}
        placeholder="Move to act…"
        onValueChange={(act_id) =>
          act_id && nodes.forEach((n) => update.mutate({ id: n.id, act_id }))
        }
        options={sortedActs(graph).map((a) => ({ value: a.id, label: a.title }))}
      />
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={() => dup.mutate(nodes.map((n) => n.id))}>
          <Copy className="size-4" /> Duplicate
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="text-danger"
          onClick={() => {
            del.mutate(nodes.map((n) => n.id))
            select([])
          }}
        >
          <Trash2 className="size-4" /> Delete
        </Button>
      </div>
    </div>
  )
}

function NodeInspector({ graph, node }: { graph: BookGraph; node: NodeOut }) {
  const bookId = graph.book.id
  const update = useUpdateNode(bookId)
  const updateBook = useUpdateBook(bookId, graph.book.series_id)
  const del = useDeleteNodes(bookId)
  const dup = useDuplicateNodes(bookId)
  const { tab, setTab, select, openNode } = useStoryStore()
  const isStart = graph.book.start_node_id === node.id
  const choicesWithoutTarget = node.choices.filter((c) =>
    c.outcomes.some((o) => !o.target_node_id),
  ).length

  const tabs: { value: InspectorTab; label: string; badge?: number; content: React.ReactNode }[] = [
    { value: 'beat', label: 'Beat', content: <BeatTab graph={graph} node={node} /> },
    {
      value: 'choices',
      label: choicesWithoutTarget ? `Choices ⚠` : 'Choices',
      badge: node.choices.length,
      content: <ChoicesTab graph={graph} node={node} />,
    },
    {
      value: 'encounters',
      label: 'Encounters',
      badge: node.encounters.length + node.items.length,
      content: <EncountersTab graph={graph} node={node} />,
    },
    {
      value: 'variants',
      label: 'Variants',
      badge: node.variants.length,
      content: <VariantsTab graph={graph} node={node} />,
    },
    { value: 'lore', label: 'Lore', content: <LoreTab graph={graph} node={node} /> },
    { value: 'art', label: 'Art', content: <ArtTab graph={graph} node={node} /> },
    { value: 'digest', label: 'Digest', content: <DigestTab graph={graph} node={node} /> },
  ]

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="space-y-2 border-b border-border p-4">
        <div className="flex items-start gap-2">
          <TextInput
            aria-label="Node title"
            value={node.title}
            onCommit={(title) =>
              title.trim() && update.mutate({ id: node.id, title: title.trim() })
            }
            className="border-transparent bg-transparent px-1 text-base font-semibold hover:border-border"
            autoFocus={node.title === 'Untitled'}
            onFocus={(e) => node.title === 'Untitled' && e.currentTarget.select()}
          />
          <Menu
            trigger={
              <Button variant="ghost" size="icon" aria-label="Node actions">
                <MoreHorizontal className="size-4" />
              </Button>
            }
          >
            <MenuItem
              icon={<Flag />}
              disabled={isStart}
              onSelect={() => updateBook.mutate({ start_node_id: node.id })}
            >
              Make this the start node
            </MenuItem>
            <MenuItem
              icon={<Copy />}
              onSelect={() =>
                dup.mutate([node.id], {
                  onSuccess: (r) => {
                    const id = r.mapping[node.id]
                    if (id) openNode(id)
                  },
                })
              }
            >
              Duplicate
            </MenuItem>
            <MenuSeparator />
            <MenuItem
              icon={<Trash2 />}
              danger
              onSelect={() => {
                del.mutate([node.id])
                select([])
              }}
            >
              Delete node
            </MenuItem>
          </Menu>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Close inspector"
            onClick={() => select([])}
          >
            <X className="size-4" />
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <TextInput
            aria-label="Node key"
            value={node.key}
            onCommit={(key) => key.trim() && update.mutate({ id: node.id, key: key.trim() })}
            className="w-40 py-1 font-mono text-xs"
            title="Key used in expressions like visits(key). Renaming updates references."
          />
          <Select
            aria-label="Act"
            value={node.act_id}
            onValueChange={(act_id) => act_id && update.mutate({ id: node.id, act_id })}
            options={sortedActs(graph).map((a) => ({ value: a.id, label: a.title }))}
            className="min-w-0 flex-1 py-1 text-xs"
          />
          {isStart && (
            <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-accent">
              <Flag className="size-3.5" aria-hidden /> Start
            </span>
          )}
        </div>
      </div>
      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as InspectorTab)}
        tabs={tabs}
        className="min-h-0 flex-1"
      />
    </div>
  )
}
