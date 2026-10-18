import {
  type QueryClient,
  type QueryKey,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import { api, unwrap } from './client'
import { qk } from './keys'
import type {
  BookGraph,
  CharacterOut,
  EnemyOut,
  FlagUsage,
  HistoryOut,
  ItemOut,
  LoreOut,
  ProblemsOut,
  RuleSystemOut,
  TableOut,
} from './types'

export { qk as queryKeys }

export function useHealth() {
  return useQuery({
    queryKey: qk.health,
    queryFn: () => unwrap(api.GET('/api/health')),
    refetchInterval: 15_000,
    retry: false,
  })
}

export function useSeriesList() {
  return useQuery({ queryKey: qk.seriesList, queryFn: () => unwrap(api.GET('/api/series')) })
}

export function useSeries(seriesId: string | undefined) {
  return useQuery({
    queryKey: qk.series(seriesId ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/series/{series_id}', { params: { path: { series_id: seriesId! } } })),
    enabled: !!seriesId,
  })
}

export function useBook(bookId: string | undefined) {
  return useQuery({
    queryKey: qk.bookInfo(bookId ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/books/{book_id}', { params: { path: { book_id: bookId! } } })),
    enabled: !!bookId,
    retry: false,
  })
}

export function useBookGraph(bookId: string | undefined) {
  return useQuery<BookGraph>({
    queryKey: qk.graph(bookId ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/books/{book_id}/graph', { params: { path: { book_id: bookId! } } })),
    enabled: !!bookId,
    retry: false,
  })
}

export function useProblems(bookId: string | undefined) {
  return useQuery<ProblemsOut>({
    queryKey: qk.problems(bookId ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/books/{book_id}/problems', { params: { path: { book_id: bookId! } } })),
    enabled: !!bookId,
  })
}

export function useHistoryState(bookId: string | undefined) {
  return useQuery<HistoryOut>({
    queryKey: qk.history(bookId ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/books/{book_id}/history', { params: { path: { book_id: bookId! } } })),
    enabled: !!bookId,
  })
}

export function useRuleSystems(seriesId: string | undefined) {
  return useQuery<RuleSystemOut[]>({
    queryKey: qk.ruleSystems(seriesId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/series/{series_id}/rule-systems', {
          params: { path: { series_id: seriesId! } },
        }),
      ),
    enabled: !!seriesId,
  })
}

export function useFlags(seriesId: string | undefined) {
  return useQuery<FlagUsage[]>({
    queryKey: qk.flags(seriesId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/series/{series_id}/flags', { params: { path: { series_id: seriesId! } } }),
      ),
    enabled: !!seriesId,
  })
}

type EntityKind = 'items' | 'enemies' | 'tables' | 'characters' | 'lore'
interface EntityTypes {
  items: ItemOut
  enemies: EnemyOut
  tables: TableOut
  characters: CharacterOut
  lore: LoreOut
}

/** Entities usable in a book (shared + book-specific). */
export function useEntities<K extends EntityKind>(
  kind: K,
  seriesId: string | undefined,
  bookId?: string,
) {
  return useQuery<EntityTypes[K][]>({
    queryKey: [...qk.entities(seriesId ?? '', kind), bookId ?? null],
    queryFn: async () => {
      const params = {
        path: { series_id: seriesId! },
        query: bookId ? { book_id: bookId } : {},
      }
      const call = {
        items: () => api.GET('/api/series/{series_id}/items', { params }),
        enemies: () => api.GET('/api/series/{series_id}/enemies', { params }),
        tables: () => api.GET('/api/series/{series_id}/tables', { params }),
        characters: () => api.GET('/api/series/{series_id}/characters', { params }),
        lore: () => api.GET('/api/series/{series_id}/lore', { params }),
      }[kind]
      return (await unwrap(
        call() as Promise<{ data?: unknown; response: Response }>,
      )) as EntityTypes[K][]
    },
    enabled: !!seriesId,
  })
}

/**
 * A mutation that refreshes the given query prefixes on success. Errors surface
 * through the global MutationCache handler (toast), so callers rarely need onError.
 */
/**
 * Refetch queries after a write. In-flight fetches are cancelled first: if a
 * query's *first* load is still running, invalidation alone would reuse that
 * request — which was sent before the write and returns stale data.
 */
export async function refresh(qc: QueryClient, keys: QueryKey[]): Promise<void> {
  await Promise.all(keys.map((queryKey) => qc.cancelQueries({ queryKey })))
  await Promise.all(keys.map((queryKey) => qc.invalidateQueries({ queryKey })))
}

export function useApiMutation<TVars, TData>(
  fn: (vars: TVars) => Promise<TData>,
  invalidate: (vars: TVars, data: TData) => QueryKey[],
  options: { onSuccess?: (data: TData, vars: TVars) => void } = {},
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: async (data, vars) => {
      await Promise.all(
        invalidate(vars, data).map((queryKey) => qc.invalidateQueries({ queryKey })),
      )
      options.onSuccess?.(data, vars)
    },
  })
}
