/** Mutation hooks. Book-scoped writes refresh graph + problems + history. */
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from './client'
import { qk } from './keys'
import { refresh, useApiMutation } from './queries'
import type {
  BookGraph,
  ChoiceCreate,
  ChoiceUpdate,
  EncounterIn,
  NodeOut,
  NodeUpdate,
  StyleGuide,
} from './types'

const book = (bookId: string) => [qk.book(bookId)]

export function useCreateSeries() {
  return useApiMutation(
    (body: { title: string; description?: string }) => unwrap(api.POST('/api/series', { body })),
    () => [qk.seriesList],
  )
}

export function useUpdateSeries() {
  return useApiMutation(
    ({ id, ...body }: { id: string; title?: string; description?: string; style?: StyleGuide }) =>
      unwrap(api.PATCH('/api/series/{series_id}', { params: { path: { series_id: id } }, body })),
    (v) => [qk.seriesList, qk.series(v.id)],
  )
}

export function useDeleteSeries() {
  return useApiMutation(
    (id: string) =>
      unwrap(api.DELETE('/api/series/{series_id}', { params: { path: { series_id: id } } })),
    () => [qk.seriesList],
  )
}

export function useCreateBook() {
  return useApiMutation(
    ({ seriesId, ...body }: { seriesId: string; title: string; synopsis?: string }) =>
      unwrap(
        api.POST('/api/series/{series_id}/books', {
          params: { path: { series_id: seriesId } },
          body,
        }),
      ),
    (v) => [qk.seriesList, qk.series(v.seriesId)],
  )
}

export function useUpdateBook(bookId: string, seriesId?: string) {
  return useApiMutation(
    (body: {
      title?: string
      synopsis?: string
      number?: number | null
      start_node_id?: string | null
    }) =>
      unwrap(api.PATCH('/api/books/{book_id}', { params: { path: { book_id: bookId } }, body })),
    () => [...book(bookId), ...(seriesId ? [qk.series(seriesId)] : []), qk.seriesList],
  )
}

export function useDeleteBook() {
  return useApiMutation(
    ({ id }: { id: string; seriesId: string }) =>
      unwrap(api.DELETE('/api/books/{book_id}', { params: { path: { book_id: id } } })),
    (v) => [qk.seriesList, qk.series(v.seriesId)],
  )
}

// ── acts ────────────────────────────────────────────────────────────────

export function useCreateAct(bookId: string) {
  return useApiMutation(
    (body: { title: string; color?: string | null }) =>
      unwrap(
        api.POST('/api/books/{book_id}/acts', { params: { path: { book_id: bookId } }, body }),
      ),
    () => book(bookId),
  )
}

export function useUpdateAct(bookId: string) {
  return useApiMutation(
    ({ id, ...body }: { id: string; title?: string; color?: string | null; summary?: string }) =>
      unwrap(api.PATCH('/api/acts/{act_id}', { params: { path: { act_id: id } }, body })),
    () => book(bookId),
  )
}

export function useDeleteAct(bookId: string) {
  return useApiMutation(
    ({ id, force }: { id: string; force?: boolean }) =>
      unwrap(
        api.DELETE('/api/acts/{act_id}', {
          params: { path: { act_id: id }, query: { force: !!force } },
        }),
      ),
    () => book(bookId),
  )
}

export function useReorderActs(bookId: string) {
  return useApiMutation(
    (ids: string[]) =>
      unwrap(
        api.PUT('/api/books/{book_id}/acts/order', {
          params: { path: { book_id: bookId } },
          body: { ids },
        }),
      ),
    () => book(bookId),
  )
}

// ── nodes ───────────────────────────────────────────────────────────────

export function useCreateNode(bookId: string) {
  return useApiMutation(
    (body: {
      act_id: string
      title?: string
      x?: number
      y?: number
      link_from?: { node_id: string; label?: string } | null
    }) =>
      unwrap(
        api.POST('/api/books/{book_id}/nodes', { params: { path: { book_id: bookId } }, body }),
      ),
    () => book(bookId),
  )
}

/** Node edits apply to the cached graph immediately and roll back on error. */
export function useUpdateNode(bookId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: NodeUpdate & { id: string }) =>
      unwrap(api.PATCH('/api/nodes/{node_id}', { params: { path: { node_id: id } }, body })),
    onMutate: async ({ id, ...body }) => {
      const key = qk.graph(bookId)
      await qc.cancelQueries({ queryKey: key })
      const previous = qc.getQueryData<BookGraph>(key)
      if (previous) {
        const simple = Object.fromEntries(
          Object.entries(body).filter(
            ([k]) => !['on_enter', 'character_ids', 'style_override'].includes(k),
          ),
        )
        qc.setQueryData<BookGraph>(key, {
          ...previous,
          nodes: previous.nodes.map((n) => (n.id === id ? ({ ...n, ...simple } as NodeOut) : n)),
        })
      }
      return { previous }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(qk.graph(bookId), ctx.previous)
    },
    onSettled: () => refresh(qc, [qk.book(bookId)]),
  })
}

export function useDeleteNodes(bookId: string) {
  return useApiMutation(
    async (ids: string[]) => {
      for (const id of ids) {
        await unwrap(api.DELETE('/api/nodes/{node_id}', { params: { path: { node_id: id } } }))
      }
    },
    () => book(bookId),
  )
}

export function useSaveLayout(bookId: string) {
  return useApiMutation(
    (positions: { id: string; x: number; y: number }[]) =>
      unwrap(
        api.PUT('/api/books/{book_id}/layout', {
          params: { path: { book_id: bookId } },
          body: { positions },
        }),
      ),
    () => book(bookId),
  )
}

export function useDuplicateNodes(bookId: string) {
  return useApiMutation(
    (node_ids: string[]) =>
      unwrap(
        api.POST('/api/books/{book_id}/duplicate', {
          params: { path: { book_id: bookId } },
          body: { node_ids, offset_x: 40, offset_y: 40 },
        }),
      ),
    () => book(bookId),
  )
}

// ── node parts ──────────────────────────────────────────────────────────

export function useCreateChoice(bookId: string) {
  return useApiMutation(
    ({ nodeId, ...body }: ChoiceCreate & { nodeId: string }) =>
      unwrap(
        api.POST('/api/nodes/{node_id}/choices', { params: { path: { node_id: nodeId } }, body }),
      ),
    () => book(bookId),
  )
}

export function useUpdateChoice(bookId: string) {
  return useApiMutation(
    ({ id, ...body }: ChoiceUpdate & { id: string }) =>
      unwrap(api.PATCH('/api/choices/{choice_id}', { params: { path: { choice_id: id } }, body })),
    () => book(bookId),
  )
}

export function useDeleteChoice(bookId: string) {
  return useApiMutation(
    (id: string) =>
      unwrap(api.DELETE('/api/choices/{choice_id}', { params: { path: { choice_id: id } } })),
    () => book(bookId),
  )
}

export function useReorderChoices(bookId: string) {
  return useApiMutation(
    ({ nodeId, ids }: { nodeId: string; ids: string[] }) =>
      unwrap(
        api.PUT('/api/nodes/{node_id}/choices/order', {
          params: { path: { node_id: nodeId } },
          body: { ids },
        }),
      ),
    () => book(bookId),
  )
}

export function useCreateVariant(bookId: string) {
  return useApiMutation(
    ({
      nodeId,
      ...body
    }: {
      nodeId: string
      label?: string
      condition?: string | null
      priority?: number
    }) =>
      unwrap(
        api.POST('/api/nodes/{node_id}/variants', { params: { path: { node_id: nodeId } }, body }),
      ),
    () => book(bookId),
  )
}

export function useUpdateVariant(bookId: string) {
  return useApiMutation(
    ({
      id,
      ...body
    }: {
      id: string
      label?: string
      condition?: string | null
      priority?: number
    }) =>
      unwrap(
        api.PATCH('/api/variants/{variant_id}', { params: { path: { variant_id: id } }, body }),
      ),
    () => book(bookId),
  )
}

export function useDeleteVariant(bookId: string) {
  return useApiMutation(
    (id: string) =>
      unwrap(api.DELETE('/api/variants/{variant_id}', { params: { path: { variant_id: id } } })),
    () => book(bookId),
  )
}

export function useCreateEncounter(bookId: string) {
  return useApiMutation(
    ({ nodeId, ...body }: EncounterIn & { nodeId: string }) =>
      unwrap(
        api.POST('/api/nodes/{node_id}/encounters', {
          params: { path: { node_id: nodeId } },
          body,
        }),
      ),
    () => book(bookId),
  )
}

export function useUpdateEncounter(bookId: string) {
  return useApiMutation(
    ({ id, ...body }: EncounterIn & { id: string }) =>
      unwrap(
        api.PUT('/api/encounters/{encounter_id}', { params: { path: { encounter_id: id } }, body }),
      ),
    () => book(bookId),
  )
}

export function useDeleteEncounter(bookId: string) {
  return useApiMutation(
    (id: string) =>
      unwrap(
        api.DELETE('/api/encounters/{encounter_id}', { params: { path: { encounter_id: id } } }),
      ),
    () => book(bookId),
  )
}

export function useSetNodeItems(bookId: string) {
  return useApiMutation(
    ({ nodeId, items }: { nodeId: string; items: { item_id: string; qty: number }[] }) =>
      unwrap(
        api.PUT('/api/nodes/{node_id}/items', {
          params: { path: { node_id: nodeId } },
          body: items,
        }),
      ),
    () => book(bookId),
  )
}

export function useSetShop(bookId: string) {
  return useApiMutation(
    ({
      nodeId,
      ...body
    }: {
      nodeId: string
      is_shop: boolean
      sell_rate: number | null
      items: { item_id: string; price: number; stock: number | null }[]
    }) =>
      unwrap(api.PUT('/api/nodes/{node_id}/shop', { params: { path: { node_id: nodeId } }, body })),
    () => book(bookId),
  )
}

export function useCreateItem(seriesId: string) {
  return useApiMutation(
    (body: { name: string; book_id?: string | null }) =>
      unwrap(
        api.POST('/api/series/{series_id}/items', {
          params: { path: { series_id: seriesId } },
          body,
        }),
      ),
    () => [qk.entities(seriesId, 'items')],
  )
}

export function useCreateEnemy(seriesId: string) {
  return useApiMutation(
    (body: { name: string; book_id?: string | null }) =>
      unwrap(
        api.POST('/api/series/{series_id}/enemies', {
          params: { path: { series_id: seriesId } },
          body,
        }),
      ),
    () => [qk.entities(seriesId, 'enemies')],
  )
}

// ── history & checkpoints ───────────────────────────────────────────────

export function useUndo(bookId: string) {
  return useApiMutation(
    () => unwrap(api.POST('/api/books/{book_id}/undo', { params: { path: { book_id: bookId } } })),
    () => book(bookId),
  )
}

export function useRedo(bookId: string) {
  return useApiMutation(
    () => unwrap(api.POST('/api/books/{book_id}/redo', { params: { path: { book_id: bookId } } })),
    () => book(bookId),
  )
}

export function useCreateCheckpoint() {
  return useApiMutation(
    (name: string) => unwrap(api.POST('/api/checkpoints', { body: { name } })),
    () => [qk.checkpoints],
  )
}

export function useRestoreCheckpoint() {
  return useApiMutation(
    (id: string) =>
      unwrap(
        api.POST('/api/checkpoints/{checkpoint_id}/restore', {
          params: { path: { checkpoint_id: id } },
        }),
      ),
    // Everything may have changed.
    () => [[]],
  )
}

export function useDeleteCheckpoint() {
  return useApiMutation(
    (id: string) =>
      unwrap(
        api.DELETE('/api/checkpoints/{checkpoint_id}', { params: { path: { checkpoint_id: id } } }),
      ),
    () => [qk.checkpoints],
  )
}
