import { ReactFlowProvider, useReactFlow } from '@xyflow/react'
import { BookX, Library } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router'
import { toast } from 'sonner'

import { ApiError } from '@/api/client'
import { useCreateNode, useDuplicateNodes, useRedo, useSaveLayout, useUndo } from '@/api/mutations'
import { useBookGraph, useEntities, useFlags, useProblems, useRuleSystems } from '@/api/queries'
import type { BookGraph } from '@/api/types'
import { rulesVocabulary, type Vocabulary, VocabularyContext } from '@/components/gbx/vocabulary'
import { buttonVariants } from '@/components/ui/button-variants'
import { EmptyState } from '@/components/ui/empty'
import { useUiStore } from '@/stores/ui'

import { BookDialog } from './BookDialog'
import { CanvasToolbar } from './CanvasToolbar'
import { autoLayout } from './canvas/autoLayout'
import { NODE_WIDTH } from './canvas/flow'
import { StoryCanvas } from './canvas/StoryCanvas'
import { Inspector } from './inspector/Inspector'
import { anyFilter, matchesFilters, matchesSearch, problemsByNode, sortedActs } from './model'
import { useStoryStore } from './storyStore'
import { useStoryShortcuts } from './useStoryShortcuts'

/** /story — reopen the last book, or point to the Library. */
export function StoryIndex() {
  const lastBookId = useUiStore((s) => s.lastBookId)
  if (lastBookId) return <Navigate to={`/story/${lastBookId}`} replace />
  return (
    <EmptyState
      icon={Library}
      title="Open a book to start writing"
      action={
        <Link to="/library" className={buttonVariants()}>
          Go to the Library
        </Link>
      }
    >
      Pick a book in the Library, or create a series and your first book there.
    </EmptyState>
  )
}

export function StoryPage() {
  const { bookId = '' } = useParams()
  const graph = useBookGraph(bookId)
  const setLastBookId = useUiStore((s) => s.setLastBookId)
  const reset = useStoryStore((s) => s.reset)

  useEffect(() => {
    reset()
  }, [bookId, reset])
  useEffect(() => {
    if (graph.isSuccess) setLastBookId(bookId)
    if (graph.error instanceof ApiError && graph.error.status === 404) setLastBookId(null)
  }, [graph.isSuccess, graph.error, bookId, setLastBookId])

  if (graph.isPending) return <p className="p-6 text-muted">Loading book…</p>
  if (graph.isError)
    return (
      <EmptyState
        icon={BookX}
        title="Book not found"
        action={
          <Link className="text-accent underline" to="/library">
            Back to the Library
          </Link>
        }
      >
        It may have been deleted.
      </EmptyState>
    )
  return (
    <ReactFlowProvider>
      <StoryWorkspace graph={graph.data} />
    </ReactFlowProvider>
  )
}

function useVocabularyFor(graph: BookGraph): Vocabulary {
  const seriesId = graph.book.series_id
  const rules = useRuleSystems(seriesId)
  const items = useEntities('items', seriesId, graph.book.id)
  const flags = useFlags(seriesId)
  return useMemo(() => {
    const active = rules.data?.find((r) => r.is_active)
    return {
      bookId: graph.book.id,
      seriesId,
      ...rulesVocabulary(active),
      items: (items.data ?? []).map((i) => ({ key: i.key, label: i.name })),
      flags: (flags.data ?? []).map((f) => ({ key: f.flag, label: f.flag })),
      nodes: graph.nodes.map((n) => ({ key: n.key, label: n.title })),
    }
  }, [graph, seriesId, rules.data, items.data, flags.data])
}

/** Nudge a position down until it doesn't cover an existing node. */
function freeSpot(graph: BookGraph, pos: { x: number; y: number }) {
  const p = { ...pos }
  const overlaps = () =>
    graph.nodes.some((n) => Math.abs(n.x - p.x) < NODE_WIDTH + 20 && Math.abs(n.y - p.y) < 130)
  for (let i = 0; i < 50 && overlaps(); i++) p.y += 140
  return p
}

function StoryWorkspace({ graph }: { graph: BookGraph }) {
  const bookId = graph.book.id
  const flow = useReactFlow()
  const problems = useProblems(bookId)
  const problemMap = useMemo(() => problemsByNode(problems.data?.problems), [problems.data])
  const vocab = useVocabularyFor(graph)
  const searchRef = useRef<HTMLInputElement>(null)
  const [bookOpen, setBookOpen] = useState(false)
  const [layingOut, setLayingOut] = useState(false)
  const { selectedIds, select, openNode, copy, clipboard, search, filters } = useStoryStore()

  const undo = useUndo(bookId)
  const redo = useRedo(bookId)
  const createNode = useCreateNode(bookId)
  const duplicate = useDuplicateNodes(bookId)
  const saveLayout = useSaveLayout(bookId)

  const matchCount = useMemo(
    () =>
      search || anyFilter(filters)
        ? graph.nodes.filter(
            (n) =>
              matchesSearch(n, search) &&
              (!anyFilter(filters) || matchesFilters(n, filters, problemMap)),
          ).length
        : null,
    [graph.nodes, search, filters, problemMap],
  )

  const doUndo = useCallback(() => {
    if (undo.isPending) return
    undo.mutate(undefined, {
      onSuccess: (r) =>
        toast(`Undid: ${r.applied}`, { action: { label: 'Redo', onClick: () => redo.mutate() } }),
    })
  }, [undo, redo])
  const doRedo = useCallback(() => {
    if (redo.isPending) return
    redo.mutate(undefined, { onSuccess: (r) => toast(`Redid: ${r.applied}`) })
  }, [redo])

  const addNode = useCallback(() => {
    const acts = sortedActs(graph)
    const selectedNode = graph.nodes.find((n) => n.id === selectedIds[0])
    const actId = selectedNode?.act_id ?? acts.at(-1)?.id
    if (!actId) return
    const center = flow.screenToFlowPosition({
      x: window.innerWidth / 2 - 200,
      y: window.innerHeight / 2,
    })
    const pos = freeSpot(
      graph,
      selectedNode ? { x: selectedNode.x + NODE_WIDTH + 80, y: selectedNode.y } : center,
    )
    createNode.mutate(
      { act_id: actId, title: 'Untitled', x: Math.round(pos.x), y: Math.round(pos.y) },
      { onSuccess: (n) => openNode(n.id, 'beat') },
    )
  }, [graph, selectedIds, flow, createNode, openNode])

  const doAutoLayout = useCallback(async () => {
    setLayingOut(true)
    try {
      const sizes = new Map(
        flow
          .getNodes()
          .filter((n) => n.type === 'story')
          .map((n) => [
            n.id,
            { width: n.measured?.width ?? NODE_WIDTH, height: n.measured?.height ?? 110 },
          ]),
      )
      const positions = await autoLayout(graph, sizes)
      await saveLayout.mutateAsync(positions)
      requestAnimationFrame(() => void flow.fitView({ padding: 0.2, duration: 400 }))
      toast('Arranged — undo to restore the previous layout')
    } finally {
      setLayingOut(false)
    }
  }, [flow, graph, saveLayout])

  const handlers = useMemo(
    () => ({
      undo: doUndo,
      redo: doRedo,
      copy: () => {
        if (selectedIds.length) {
          copy(selectedIds)
          toast(`Copied ${selectedIds.length} node${selectedIds.length === 1 ? '' : 's'}`)
        }
      },
      paste: () => {
        const ids = clipboard.filter((id) => graph.nodes.some((n) => n.id === id))
        if (ids.length)
          duplicate.mutate(ids, { onSuccess: (r) => select(Object.values(r.mapping).sort()) })
      },
      duplicate: () => {
        if (selectedIds.length)
          duplicate.mutate(selectedIds, {
            onSuccess: (r) => select(Object.values(r.mapping).sort()),
          })
      },
      newNode: addNode,
      fit: () => void flow.fitView({ padding: 0.2, duration: 300 }),
      focusSearch: () => searchRef.current?.focus(),
      deselect: () => select([]),
    }),
    [doUndo, doRedo, selectedIds, copy, clipboard, graph.nodes, duplicate, select, addNode, flow],
  )
  useStoryShortcuts(handlers)

  return (
    <VocabularyContext.Provider value={vocab}>
      <div className="grid h-full min-h-0 grid-cols-[minmax(0,1fr)_auto]">
        <div className="flex min-h-0 min-w-0 flex-col">
          <CanvasToolbar
            graph={graph}
            searchRef={searchRef}
            matchCount={matchCount}
            onAddNode={addNode}
            onAutoLayout={() => void doAutoLayout()}
            onFit={handlers.fit}
            onUndo={doUndo}
            onRedo={doRedo}
            onOpenBook={() => setBookOpen(true)}
            busy={undo.isPending || redo.isPending || layingOut}
          />
          <div className="min-h-0 flex-1">
            <StoryCanvas graph={graph} problems={problemMap} />
          </div>
        </div>
        <aside
          aria-label="Inspector"
          className="flex w-[min(420px,40vw)] min-w-80 flex-col border-l border-border bg-surface"
        >
          <Inspector graph={graph} />
        </aside>
      </div>
      <BookDialog graph={graph} open={bookOpen} onOpenChange={setBookOpen} />
    </VocabularyContext.Provider>
  )
}
