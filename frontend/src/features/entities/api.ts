import { type QueryKey, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from '@/api/client'
import { qk } from '@/api/keys'
import { refresh, useApiMutation } from '@/api/queries'
import type { components } from '@/api/schema'

type S = components['schemas']
export type EntityPlural = 'enemies' | 'items' | 'tables'
export type EnemyCreate = S['EnemyCreate']
export type EnemyUpdate = S['EnemyUpdate']
export type ItemUpdate = S['ItemUpdate']
export type TableUpdate = S['TableUpdate']

const ek = {
  whereUsed: (seriesId: string, type: string, key: string) =>
    ['entities', seriesId, 'where-used', type, key] as const,
  totals: (seriesId: string) => ['entities', seriesId, 'item-totals'] as const,
  problems: (seriesId: string) => ['entities', seriesId, 'problems'] as const,
  levels: (enemyId: string) => ['entities', 'enemy-levels', enemyId] as const,
}

/** Everything an entity edit can affect in this series (lists, uses, problems, levels). */
const affected = (seriesId: string): QueryKey[] => [
  ['entities', seriesId],
  ['entities', 'enemy-levels'],
  ['book'],
]

export function useWhereUsed(seriesId: string, targetType: string, key: string | undefined) {
  return useQuery({
    queryKey: ek.whereUsed(seriesId, targetType, key ?? ''),
    staleTime: 0,
    queryFn: () =>
      unwrap(
        api.GET('/api/series/{series_id}/where-used', {
          params: {
            path: { series_id: seriesId },
            query: { target_type: targetType as never, key: key! },
          },
        }),
      ),
    enabled: !!key,
  })
}

export function useItemTotals(seriesId: string) {
  return useQuery({
    queryKey: ek.totals(seriesId),
    staleTime: 0,
    queryFn: () =>
      unwrap(
        api.GET('/api/series/{series_id}/item-totals', {
          params: { path: { series_id: seriesId } },
        }),
      ),
  })
}

export function useEntityProblems(seriesId: string) {
  return useQuery({
    queryKey: ek.problems(seriesId),
    staleTime: 0,
    queryFn: () =>
      unwrap(
        api.GET('/api/series/{series_id}/entity-problems', {
          params: { path: { series_id: seriesId } },
        }),
      ),
  })
}

export function useEnemyLevels(enemyId: string | undefined, levelTo = 10) {
  return useQuery({
    queryKey: [...ek.levels(enemyId ?? ''), levelTo],
    staleTime: 0,
    queryFn: () =>
      unwrap(
        api.GET('/api/enemies/{enemy_id}/levels', {
          params: { path: { enemy_id: enemyId! }, query: { level_from: 1, level_to: levelTo } },
        }),
      ),
    enabled: !!enemyId,
    placeholderData: (prev) => prev,
  })
}

export function useCreateEntity(plural: EntityPlural, seriesId: string) {
  return useApiMutation(
    (body: { name: string; book_id?: string | null }) => {
      const params = { params: { path: { series_id: seriesId } }, body }
      const call = {
        enemies: () => api.POST('/api/series/{series_id}/enemies', params),
        items: () => api.POST('/api/series/{series_id}/items', params),
        tables: () => api.POST('/api/series/{series_id}/tables', params),
      }[plural]
      return unwrap(call() as Promise<{ data?: { id: string }; response: Response }>) as Promise<{
        id: string
      }>
    },
    () => affected(seriesId),
  )
}

type EntityOut = { enemies: S['EnemyOut']; items: S['ItemOut']; tables: S['TableOut'] }
type EntityPatch = { enemies: EnemyUpdate; items: ItemUpdate; tables: TableUpdate }

function patchEntity<P extends EntityPlural>(plural: P, id: string, body: EntityPatch[P]) {
  const params = { params: { path: { entity_id: id } } }
  const call = {
    enemies: () => api.PATCH('/api/enemies/{entity_id}', { ...params, body: body as EnemyUpdate }),
    items: () => api.PATCH('/api/items/{entity_id}', { ...params, body: body as ItemUpdate }),
    tables: () => api.PATCH('/api/tables/{entity_id}', { ...params, body: body as TableUpdate }),
  }[plural]
  return unwrap(call() as Promise<{ data?: unknown; response: Response }>)
}

/**
 * Save edits to one kind of entity. Each edit is applied to the cached list
 * synchronously and saved in order; list edits pass a function of the latest
 * value, so a blur-commit followed by a click (e.g. "Add row") never rebuilds
 * the list from pre-edit props. The server is refetched once the queue empties.
 */
export function useSaveEntity<P extends EntityPlural>(plural: P, seriesId: string) {
  const qc = useQueryClient()
  const listKey = qk.entities(seriesId, plural)
  const mutationKey = ['entity-save', seriesId, plural]
  const m = useMutation({
    mutationKey,
    scope: { id: `entity-save:${seriesId}:${plural}` },
    mutationFn: ({ id, body }: { id: string; body: EntityPatch[P] }) =>
      patchEntity(plural, id, body),
    onSettled: async () => {
      if (qc.isMutating({ mutationKey }) <= 1) await refresh(qc, affected(seriesId))
    },
  })
  return (id: string, patch: EntityPatch[P] | ((current: EntityOut[P]) => EntityPatch[P])) => {
    const current = qc
      .getQueriesData<EntityOut[P][]>({ queryKey: listKey })
      .flatMap(([, d]) => d ?? [])
      .find((e) => e.id === id)
    if (!current) return
    const body = typeof patch === 'function' ? patch(current) : patch
    void qc.cancelQueries({ queryKey: listKey })
    qc.setQueriesData<EntityOut[P][]>({ queryKey: listKey }, (d) =>
      d?.map((e) => (e.id === id ? ({ ...e, ...body } as EntityOut[P]) : e)),
    )
    m.mutate({ id, body })
  }
}

export function useDeleteEntity(plural: EntityPlural, seriesId: string) {
  return useApiMutation(
    ({ id, force }: { id: string; force?: boolean }) => {
      const params = { params: { path: { entity_id: id }, query: { force: !!force } } }
      const call = {
        enemies: () => api.DELETE('/api/enemies/{entity_id}', params),
        items: () => api.DELETE('/api/items/{entity_id}', params),
        tables: () => api.DELETE('/api/tables/{entity_id}', params),
      }[plural]
      return unwrap(call() as Promise<{ data?: unknown; response: Response }>)
    },
    () => affected(seriesId),
  )
}
