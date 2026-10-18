import '@xyflow/react/dist/style.css'

import {
  Background,
  BackgroundVariant,
  type Connection,
  Controls,
  type FinalConnectionState,
  MarkerType,
  MiniMap,
  type NodeChange,
  type OnBeforeDelete,
  ReactFlow,
  applyNodeChanges,
  useReactFlow,
} from '@xyflow/react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  useCreateChoice,
  useCreateNode,
  useDeleteChoice,
  useDeleteNodes,
  useSaveLayout,
  useUpdateChoice,
  useUpdateNode,
} from '@/api/mutations'
import type { BookGraph, NodeOut } from '@/api/types'
import { useResolvedTheme } from '@/app/useTheme'

import { anyFilter, matchesFilters, matchesSearch, type ProblemSummary, sortedActs } from '../model'
import { useStoryStore } from '../storyStore'
import { ActFrame } from './ActFrame'
import { ChoiceEdge } from './ChoiceEdge'
import { NodeCard } from './NodeCard'
import {
  type ActFrameNode,
  type ChoiceFlowEdge,
  NODE_WIDTH,
  type StoryFlowNode,
  actAt,
  buildEdges,
  buildNodes,
  computeFrames,
} from './flow'

// Defined at module level so React Flow sees stable component identities.
const nodeTypes = { story: NodeCard, act: ActFrame }
const edgeTypes = { choice: ChoiceEdge }

export function StoryCanvas({
  graph,
  problems,
}: {
  graph: BookGraph
  problems: Map<string, ProblemSummary>
}) {
  const bookId = graph.book.id
  const flow = useReactFlow<StoryFlowNode | ActFrameNode, ChoiceFlowEdge>()
  const theme = useResolvedTheme()
  const { selectedIds, select, openNode, search, filters, revealId, reveal } = useStoryStore()

  const createNode = useCreateNode(bookId)
  const updateNode = useUpdateNode(bookId)
  const deleteNodes = useDeleteNodes(bookId)
  const saveLayout = useSaveLayout(bookId)
  const createChoice = useCreateChoice(bookId)
  const updateChoice = useUpdateChoice(bookId)
  const deleteChoice = useDeleteChoice(bookId)

  const isVisible = useCallback(
    (n: NodeOut) =>
      matchesSearch(n, search) && (!anyFilter(filters) || matchesFilters(n, filters, problems)),
    [search, filters, problems],
  )

  // Story nodes live in local state so dragging is smooth; server data is merged in.
  const [nodes, setNodes] = useState<StoryFlowNode[]>([])
  useEffect(() => {
    const selected = new Set(selectedIds)
    setNodes((prev) => {
      const before = new Map(prev.map((n) => [n.id, n]))
      return buildNodes(graph, problems, isVisible).map((n) => ({
        ...n,
        measured: before.get(n.id)?.measured,
        selected: selected.has(n.id),
      }))
    })
    // selectedIds intentionally excluded: selection flows from React Flow to the store.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, problems, isVisible])

  const addNodeInAct = useCallback(
    (actId: string) => {
      const members = graph.nodes.filter((n) => n.act_id === actId)
      const x = members.length ? Math.max(...members.map((n) => n.x)) + NODE_WIDTH + 80 : 0
      const y = members.length ? Math.min(...members.map((n) => n.y)) : 0
      createNode.mutate(
        { act_id: actId, title: 'Untitled', x, y },
        { onSuccess: (n) => openNode(n.id, 'beat') },
      )
    },
    [graph.nodes, createNode, openNode],
  )

  const frames = useMemo(
    () =>
      computeFrames(graph, nodes).map((f) => ({ ...f, data: { ...f.data, onAdd: addNodeInAct } })),
    [graph, nodes, addNodeInAct],
  )
  const edges = useMemo(() => buildEdges(graph, isVisible), [graph, isVisible])
  const allNodes = useMemo(() => [...frames, ...nodes], [frames, nodes])

  // Selections made outside the canvas (inspector, problems panel, palette)
  // are mirrored into React Flow's node state.
  useEffect(() => {
    const want = new Set(selectedIds)
    setNodes((ns) =>
      ns.some((n) => !!n.selected !== want.has(n.id))
        ? ns.map((n) => ({ ...n, selected: want.has(n.id) }))
        : ns,
    )
  }, [selectedIds])

  // The store is the source of truth for selection. User selections reach it
  // via "select" node changes; programmatic selections are mirrored in above.
  // (React Flow's onSelectionChange would echo our own updates back, briefly
  // reporting an empty selection while a just-created node is still loading.)
  const onNodesChange = useCallback(
    (changes: NodeChange<StoryFlowNode | ActFrameNode>[]) => {
      const storyChanges = changes.filter(
        (c) => !('id' in c) || !c.id.startsWith('act:'),
      ) as NodeChange<StoryFlowNode>[]
      setNodes((ns) => applyNodeChanges(storyChanges, ns))
      const selection = storyChanges.filter((c) => c.type === 'select')
      if (selection.length) {
        const current = new Set(useStoryStore.getState().selectedIds)
        for (const c of selection) {
          if (c.selected) current.add(c.id)
          else current.delete(c.id)
        }
        select([...current].sort())
      }
    },
    [select],
  )

  // Reveal requests (from search, problems panel, palette, ?node= links).
  // Fit the whole book on open, unless a reveal is waiting: the initial fit would
  // override its centring. (A ?node= link may not have reached the store yet when
  // the canvas mounts in the same commit, hence the URL check.)
  const [fitOnOpen] = useState(
    () =>
      !useStoryStore.getState().revealId &&
      !new URLSearchParams(window.location.search).has('node'),
  )
  useEffect(() => {
    if (!revealId) return
    const n = nodes.find((x) => x.id === revealId)
    if (n) {
      void flow.setCenter(n.position.x + NODE_WIDTH / 2, n.position.y + 50, {
        zoom: 1.1,
        duration: 400,
      })
      reveal(null)
    }
  }, [revealId, nodes, flow, reveal])

  // ── drag: persist positions; dropping into another act's frame moves it there ──
  const dragStartFrames = useRef<ActFrameNode[]>([])
  const onNodeDragStart = useCallback(() => {
    dragStartFrames.current = frames
  }, [frames])
  const onNodeDragStop = useCallback(
    (_: unknown, node: StoryFlowNode | ActFrameNode, dragged: (StoryFlowNode | ActFrameNode)[]) => {
      const moved = (dragged.length ? dragged : [node]).filter(
        (n): n is StoryFlowNode => n.type === 'story',
      )
      if (!moved.length) return
      if (moved.length === 1) {
        const n = moved[0]!
        const cx = n.position.x + (n.measured?.width ?? NODE_WIDTH) / 2
        const cy = n.position.y + 20
        const target = actAt(
          dragStartFrames.current.filter((f) => f.data.act.id !== n.data.node.act_id),
          cx,
          cy,
        )
        if (target) {
          updateNode.mutate({ id: n.id, act_id: target, x: n.position.x, y: n.position.y })
          return
        }
      }
      saveLayout.mutate(
        moved.map((n) => ({ id: n.id, x: Math.round(n.position.x), y: Math.round(n.position.y) })),
      )
    },
    [saveLayout, updateNode],
  )

  // ── linking ──
  const onConnect = useCallback(
    (c: Connection) => {
      if (!c.source || !c.target) return
      createChoice.mutate(
        { nodeId: c.source, label: '', target_node_id: c.target },
        { onSuccess: (choice) => openNode(c.source, 'choices', choice.id) },
      )
    },
    [createChoice, openNode],
  )

  const onConnectEnd = useCallback(
    (event: MouseEvent | TouchEvent, state: FinalConnectionState) => {
      if (state.isValid || !state.fromNode || state.fromNode.type !== 'story') return
      const point = 'changedTouches' in event ? event.changedTouches[0]! : event
      const pos = flow.screenToFlowPosition({ x: point.clientX, y: point.clientY })
      const source = state.fromNode as unknown as StoryFlowNode
      const actId = actAt(frames, pos.x, pos.y) ?? source.data.node.act_id
      createNode.mutate(
        {
          act_id: actId,
          title: 'Untitled',
          x: Math.round(pos.x),
          y: Math.round(pos.y - 30),
          link_from: { node_id: source.id, label: '' },
        },
        { onSuccess: (n) => openNode(n.id, 'beat') },
      )
    },
    [flow, frames, createNode, openNode],
  )

  // ── double-click on empty canvas creates a node there ──
  const onPaneClick = useCallback(
    (event: React.MouseEvent) => {
      if (event.detail !== 2) return
      const pos = flow.screenToFlowPosition({ x: event.clientX, y: event.clientY })
      const actId = actAt(frames, pos.x, pos.y) ?? sortedActs(graph).at(-1)?.id
      if (!actId) return
      createNode.mutate(
        {
          act_id: actId,
          title: 'Untitled',
          x: Math.round(pos.x - NODE_WIDTH / 2),
          y: Math.round(pos.y - 30),
        },
        { onSuccess: (n) => openNode(n.id, 'beat') },
      )
    },
    [flow, frames, graph, createNode, openNode],
  )

  // ── deletion goes through the API (undoable), never React Flow's local delete ──
  const onBeforeDelete: OnBeforeDelete<StoryFlowNode | ActFrameNode, ChoiceFlowEdge> = useCallback(
    async ({ nodes: delNodes, edges: delEdges }) => {
      const nodeIds = delNodes.filter((n) => n.type === 'story').map((n) => n.id)
      if (nodeIds.length) {
        deleteNodes.mutate(nodeIds)
        select([])
        return false
      }
      for (const e of delEdges) {
        const choice = e.data?.choice
        if (!choice) continue
        if (choice.kind === 'goto') deleteChoice.mutate(choice.id)
        else
          updateChoice.mutate({
            id: choice.id,
            outcomes: choice.outcomes.map((o) => ({
              key: o.key,
              target_node_id: o.key === e.data?.outcomeKey ? null : o.target_node_id,
              range_lo: o.range_lo,
              range_hi: o.range_hi,
            })),
          })
      }
      return false
    },
    [deleteNodes, deleteChoice, updateChoice, select],
  )

  return (
    <ReactFlow<StoryFlowNode | ActFrameNode, ChoiceFlowEdge>
      nodes={allNodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      colorMode={theme}
      onNodesChange={onNodesChange}
      onNodeDragStart={onNodeDragStart}
      onNodeDragStop={onNodeDragStop}
      onConnect={onConnect}
      onConnectEnd={onConnectEnd}
      onPaneClick={onPaneClick}
      onBeforeDelete={onBeforeDelete}
      onEdgeClick={(_, e) => e.data && openNode(e.source, 'choices', e.data.choice.id)}
      onNodeDoubleClick={(_, n) => n.type === 'story' && openNode(n.id, 'beat')}
      defaultEdgeOptions={{ markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 } }}
      fitView={fitOnOpen}
      fitViewOptions={{ padding: 0.15, maxZoom: 1 }}
      zoomOnDoubleClick={false}
      deleteKeyCode={['Delete', 'Backspace']}
      multiSelectionKeyCode={['Shift', 'Meta', 'Control']}
      selectionOnDrag={false}
      minZoom={0.1}
      maxZoom={2}
      proOptions={{ hideAttribution: true }}
      aria-label="Story graph"
    >
      <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
      <MiniMap
        pannable
        zoomable
        nodeColor={(n) =>
          n.type === 'act' ? 'transparent' : ((n.data as { actColor?: string }).actColor ?? '#888')
        }
        nodeStrokeColor={(n) =>
          n.type === 'act' ? ((n.data as { color?: string }).color ?? '#888') : 'transparent'
        }
        className="!rounded-lg !border !border-border"
      />
      <Controls showInteractive={false} className="!rounded-lg !border !border-border !shadow-sm" />
    </ReactFlow>
  )
}
