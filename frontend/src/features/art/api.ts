import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMutation } from '@tanstack/react-query'

import { api, ApiError, unwrap } from '@/api/client'
import { useApiMutation } from '@/api/queries'
import type { components } from '@/api/schema'

type S = components['schemas']
export type Asset = S['AssetOut']
export type AssetUse = S['AssetUse']
/** The API fills every layout field (pydantic defaults); the generated types mark them optional. */
export type PrintLayout = Required<S['PrintLayout']>
export type DigitalLayout = Required<S['DigitalLayout']>
export type Placement = Omit<S['ArtPlacementOut'], 'layout' | 'digital'> & {
  layout: PrintLayout
  digital: DigitalLayout
}
export type PlacementIn = S['ArtPlacementIn']
export type PlacementUpdate = S['ArtPlacementUpdate']
export type PageSetup = Required<S['PageSetupOut']>
export type ArtMap = S['MapOut']
export type Marker = S['Marker']
export type AppendixOptions = Required<S['AppendixOptions']>
export type Appendix = Omit<S['AppendixOut'], 'options'> & { options: AppendixOptions }
export type ShotRow = S['ShotRow']
export type TargetType = PlacementIn['target_type']

/**
 * Library data is per series; book art lives under ['book', id] so undo/redo
 * (which invalidates the book) refreshes it.
 */
export const artKeys = {
  assets: (seriesId: string) => ['art', seriesId, 'assets'] as const,
  uses: (assetId: string) => ['art', 'uses', assetId] as const,
  bookPlacements: (bookId: string) => ['book', bookId, 'art'] as const,
  targetPlacements: (type: string, id: string) => ['art', 'placements', type, id] as const,
  setup: (bookId: string) => ['book', bookId, 'page-setup'] as const,
  maps: (seriesId: string) => ['art', seriesId, 'maps'] as const,
  appendices: (bookId: string) => ['book', bookId, 'appendices'] as const,
  render: (id: string) => ['appendix', id, 'render'] as const,
  shots: (seriesId: string) => ['art', seriesId, 'shots'] as const,
}

// ── assets ──────────────────────────────────────────────────────────────

export function useAssets(seriesId: string | undefined) {
  return useQuery({
    queryKey: artKeys.assets(seriesId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/series/{series_id}/assets', { params: { path: { series_id: seriesId! } } }),
      ),
    enabled: !!seriesId,
  })
}

/** Raw-body upload (the endpoint takes the image bytes, not a form). */
export async function uploadAsset(seriesId: string, file: File) {
  const res = await fetch(
    `/api/series/${seriesId}/assets?filename=${encodeURIComponent(file.name)}`,
    {
      method: 'POST',
      body: file,
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
    },
  )
  const body = (await res.json().catch(() => ({}))) as { detail?: string; code?: string }
  if (!res.ok)
    throw new ApiError(res.status, body.code ?? `http_${res.status}`, body.detail ?? res.statusText)
  return body as unknown as S['AssetUploadOut']
}

export function useUploadAssets(seriesId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (files: File[]) => {
      const done: S['AssetUploadOut'][] = []
      const failed: { name: string; error: string }[] = []
      for (const f of files) {
        try {
          done.push(await uploadAsset(seriesId, f))
        } catch (e) {
          failed.push({ name: f.name, error: e instanceof Error ? e.message : String(e) })
        }
      }
      return { done, failed }
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: artKeys.assets(seriesId) }),
  })
}

export function useUpdateAsset(seriesId: string) {
  return useApiMutation(
    ({ id, ...body }: S['AssetUpdate'] & { id: string }) =>
      unwrap(api.PATCH('/api/assets/{asset_id}', { params: { path: { asset_id: id } }, body })),
    () => [artKeys.assets(seriesId)],
  )
}

export function useDeleteAsset(seriesId: string) {
  return useApiMutation(
    ({ id, force }: { id: string; force?: boolean }) =>
      unwrap(
        api.DELETE('/api/assets/{asset_id}', {
          params: { path: { asset_id: id }, query: { force: !!force } },
        }),
      ),
    () => [artKeys.assets(seriesId), ['art'], ['book']],
  )
}

export function useAssetUses(assetId: string | null) {
  return useQuery({
    queryKey: artKeys.uses(assetId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/assets/{asset_id}/where-used', { params: { path: { asset_id: assetId! } } }),
      ),
    enabled: !!assetId,
  })
}

// ── placements ──────────────────────────────────────────────────────────

export function useBookPlacements(bookId: string | undefined) {
  return useQuery({
    queryKey: artKeys.bookPlacements(bookId ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/placements', { params: { query: { book_id: bookId! } } })) as Promise<
        Placement[]
      >,
    enabled: !!bookId,
  })
}

export function useTargetPlacements(type: TargetType, id: string | undefined) {
  return useQuery({
    queryKey: artKeys.targetPlacements(type, id ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/placements', { params: { query: { target_type: type, target_id: id! } } }),
      ) as Promise<Placement[]>,
    enabled: !!id,
  })
}

/** Everything that shows placements: the book, the target, the library's use counts. */
const placementKeys = (seriesId: string | undefined) => [
  ['book'],
  ['art', 'placements'],
  ['art', 'uses'],
  ...(seriesId ? [artKeys.assets(seriesId), artKeys.shots(seriesId)] : []),
]

export function useCreatePlacement(seriesId: string | undefined) {
  return useApiMutation(
    (body: PlacementIn) => unwrap(api.POST('/api/placements', { body })) as Promise<Placement>,
    () => placementKeys(seriesId),
  )
}

export function useUpdatePlacement(seriesId: string | undefined) {
  return useApiMutation(
    ({ id, ...body }: PlacementUpdate & { id: string }) =>
      unwrap(
        api.PATCH('/api/placements/{placement_id}', {
          params: { path: { placement_id: id } },
          body,
        }),
      ),
    () => placementKeys(seriesId),
  )
}

export function useDeletePlacement(seriesId: string | undefined) {
  return useApiMutation(
    (id: string) =>
      unwrap(
        api.DELETE('/api/placements/{placement_id}', { params: { path: { placement_id: id } } }),
      ),
    () => placementKeys(seriesId),
  )
}

export function useReorderPlacements(seriesId: string | undefined) {
  return useApiMutation(
    (ids: string[]) => unwrap(api.POST('/api/placements/reorder', { body: { ids } })),
    () => placementKeys(seriesId),
  )
}

// ── page setup ──────────────────────────────────────────────────────────

export function usePageSetup(bookId: string | undefined) {
  return useQuery({
    queryKey: artKeys.setup(bookId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/books/{book_id}/page-setup', { params: { path: { book_id: bookId! } } }),
      ) as Promise<PageSetup>,
    enabled: !!bookId,
  })
}

export function useSavePageSetup(bookId: string) {
  return useApiMutation(
    (body: S['PageSetup']) =>
      unwrap(
        api.PUT('/api/books/{book_id}/page-setup', { params: { path: { book_id: bookId } }, body }),
      ),
    () => [['book', bookId]],
  )
}

// ── maps ────────────────────────────────────────────────────────────────

export function useMaps(seriesId: string | undefined) {
  return useQuery({
    queryKey: artKeys.maps(seriesId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/series/{series_id}/maps', { params: { path: { series_id: seriesId! } } }),
      ),
    enabled: !!seriesId,
  })
}

const mapKeys = (seriesId: string) => [artKeys.maps(seriesId), artKeys.assets(seriesId), ['book']]

export function useCreateMap(seriesId: string) {
  return useApiMutation(
    (body: S['MapIn']) =>
      unwrap(
        api.POST('/api/series/{series_id}/maps', {
          params: { path: { series_id: seriesId } },
          body,
        }),
      ),
    () => mapKeys(seriesId),
  )
}

export function useUpdateMap(seriesId: string) {
  return useApiMutation(
    ({ id, ...body }: S['MapUpdate'] & { id: string }) =>
      unwrap(api.PATCH('/api/maps/{map_id}', { params: { path: { map_id: id } }, body })),
    () => mapKeys(seriesId),
  )
}

export function useDeleteMap(seriesId: string) {
  return useApiMutation(
    (id: string) => unwrap(api.DELETE('/api/maps/{map_id}', { params: { path: { map_id: id } } })),
    () => mapKeys(seriesId),
  )
}

// ── appendices ──────────────────────────────────────────────────────────

export function useAppendices(bookId: string | undefined) {
  return useQuery({
    queryKey: artKeys.appendices(bookId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/books/{book_id}/appendices', { params: { path: { book_id: bookId! } } }),
      ) as Promise<Appendix[]>,
    enabled: !!bookId,
  })
}

const appendixKeys = (bookId: string) => [artKeys.appendices(bookId), ['appendix']]

export function useCreateAppendix(bookId: string) {
  return useApiMutation(
    (body: S['AppendixIn']) =>
      unwrap(
        api.POST('/api/books/{book_id}/appendices', {
          params: { path: { book_id: bookId } },
          body,
        }),
      ),
    () => appendixKeys(bookId),
  )
}

export function useUpdateAppendix(bookId: string) {
  return useApiMutation(
    ({ id, ...body }: S['AppendixUpdate'] & { id: string }) =>
      unwrap(
        api.PATCH('/api/appendices/{appendix_id}', { params: { path: { appendix_id: id } }, body }),
      ),
    () => appendixKeys(bookId),
  )
}

export function useDeleteAppendix(bookId: string) {
  return useApiMutation(
    (id: string) =>
      unwrap(
        api.DELETE('/api/appendices/{appendix_id}', { params: { path: { appendix_id: id } } }),
      ),
    () => appendixKeys(bookId),
  )
}

export function useReorderAppendices(bookId: string) {
  return useApiMutation(
    (ids: string[]) =>
      unwrap(
        api.POST('/api/books/{book_id}/appendices/reorder', {
          params: { path: { book_id: bookId } },
          body: { ids },
        }),
      ),
    () => appendixKeys(bookId),
  )
}

export function useAppendixRender(id: string | null) {
  return useQuery({
    queryKey: artKeys.render(id ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/appendices/{appendix_id}/render', { params: { path: { appendix_id: id! } } }),
      ),
    enabled: !!id,
    staleTime: 0,
  })
}

export function useCodex(
  bookId: string,
  body: { tier: string; enemies: string[]; items: string[] } | null,
) {
  return useQuery({
    queryKey: ['book', bookId, 'codex', body],
    queryFn: () =>
      unwrap(
        api.POST('/api/books/{book_id}/codex', {
          params: { path: { book_id: bookId } },
          body: body!,
        }),
      ),
    enabled: !!body,
  })
}

// ── commissioning ───────────────────────────────────────────────────────

export function useShotList(seriesId: string | undefined) {
  return useQuery({
    queryKey: artKeys.shots(seriesId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/series/{series_id}/shot-list', {
          params: { path: { series_id: seriesId! } },
        }),
      ),
    enabled: !!seriesId,
  })
}

export const ROLE_LABELS: Record<string, string> = {
  illustration: 'Illustration',
  opener: 'Act opener',
  cover_front: 'Front cover',
  cover_back: 'Back cover',
  frontispiece: 'Frontispiece',
  title_page: 'Title page',
  endpaper: 'Endpaper',
  portrait: 'Portrait',
  image: 'Image',
}

export const STATUS_LABELS: Record<string, string> = {
  needed: 'Needed',
  sketch: 'Sketch',
  final: 'Final',
}

/** A default page for targets outside a book (entity portraits). */
export const DEFAULT_SETUP: PageSetup = {
  trim_width_mm: 152.4,
  trim_height_mm: 228.6,
  margin_inner_mm: 19,
  margin_outer_mm: 16,
  margin_top_mm: 18,
  margin_bottom_mm: 22,
  bleed_mm: 3.175,
  text_width: 117.4,
  text_height: 188.6,
}
