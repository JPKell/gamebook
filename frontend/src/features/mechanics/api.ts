import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, unwrap } from '@/api/client'
import type { components } from '@/api/schema'
import { qk } from '@/api/keys'
import { refresh, useApiMutation } from '@/api/queries'
import type { RuleSystemOut } from '@/api/types'

import type { RuleSystemDef } from './defs'

const mk = {
  all: (rsId: string) => ['mechanics', rsId] as const,
  tier: (rsId: string, tier: string) => ['mechanics', rsId, 'tier', tier] as const,
  problems: (rsId: string) => ['mechanics', rsId, 'problems'] as const,
}

export function useTierView(rsId: string | undefined, tier: string | undefined) {
  return useQuery({
    queryKey: mk.tier(rsId ?? '', tier ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/rule-systems/{rule_system_id}/tiers/{tier}', {
          params: { path: { rule_system_id: rsId!, tier: tier! } },
        }),
      ),
    enabled: !!rsId && !!tier,
    retry: false,
    placeholderData: (prev) => prev,
  })
}

export function useRuleProblems(rsId: string | undefined) {
  return useQuery({
    queryKey: mk.problems(rsId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/rule-systems/{rule_system_id}/problems', {
          params: { path: { rule_system_id: rsId! } },
        }),
      ),
    enabled: !!rsId,
  })
}

/**
 * Save a whole definition. Optimistic (the editor stays snappy) and serialised
 * per rule system, so rapid edits apply in order and each builds on the last.
 */
export function useSaveDefinition(seriesId: string, rsId: string) {
  const qc = useQueryClient()
  const mutationKey = ['rules', rsId]
  // Refetch only once the queue is empty: refetching between queued edits would
  // overwrite later optimistic edits with older server state (and the next edit
  // would then be built from it, silently dropping one).
  const settle = async () => {
    if (qc.isMutating({ mutationKey }) <= 1)
      await refresh(qc, [qk.ruleSystems(seriesId), mk.all(rsId)])
  }
  return useMutation({
    mutationKey,
    scope: { id: `rules:${rsId}` },
    mutationFn: (definition: RuleSystemDef) =>
      unwrap(
        api.PATCH('/api/rule-systems/{rule_system_id}', {
          params: { path: { rule_system_id: rsId } },
          body: { definition },
        }),
      ),
    onMutate: async (definition) => {
      const key = qk.ruleSystems(seriesId)
      await qc.cancelQueries({ queryKey: key })
      const previous = qc.getQueryData<RuleSystemOut[]>(key)
      if (previous)
        qc.setQueryData<RuleSystemOut[]>(
          key,
          previous.map((r) => (r.id === rsId ? { ...r, definition } : r)),
        )
    },
    // On error the server is the source of truth: resync rather than restoring a
    // snapshot that may predate other queued edits.
    onSettled: settle,
  })
}

export function useCreateRuleSystem(seriesId: string) {
  return useApiMutation(
    (body: { name: string; definition?: RuleSystemDef; is_active?: boolean }) =>
      unwrap(
        api.POST('/api/series/{series_id}/rule-systems', {
          params: { path: { series_id: seriesId } },
          body,
        }),
      ),
    () => [qk.ruleSystems(seriesId)],
  )
}

export function useUpdateRuleSystemMeta(seriesId: string) {
  return useApiMutation(
    ({ id, ...body }: { id: string; name?: string; is_active?: boolean }) =>
      unwrap(
        api.PATCH('/api/rule-systems/{rule_system_id}', {
          params: { path: { rule_system_id: id } },
          body,
        }),
      ),
    (v) => [qk.ruleSystems(seriesId), mk.all(v.id)],
  )
}

export function useDeleteRuleSystem(seriesId: string) {
  return useApiMutation(
    (id: string) =>
      unwrap(
        api.DELETE('/api/rule-systems/{rule_system_id}', {
          params: { path: { rule_system_id: id } },
        }),
      ),
    () => [qk.ruleSystems(seriesId)],
  )
}

export type LabBody = components['schemas']['LabIn']
export type SweepBody = components['schemas']['SweepIn']

function runLab(seriesId: string, body: LabBody) {
  return unwrap(
    api.POST('/api/series/{series_id}/combat-lab', {
      params: { path: { series_id: seriesId } },
      body,
    }),
  )
}

function runSweep(seriesId: string, body: SweepBody) {
  return unwrap(
    api.POST('/api/series/{series_id}/combat-lab/sweep', {
      params: { path: { series_id: seriesId } },
      body,
    }),
  )
}

export function useCombatLab(seriesId: string) {
  return useMutation({ mutationFn: (body: LabBody) => runLab(seriesId, body) })
}

export function useCombatSweep(seriesId: string) {
  return useMutation({ mutationFn: (body: SweepBody) => runSweep(seriesId, body) })
}

export type LabResult = Awaited<ReturnType<typeof runLab>>
export type SweepResult = Awaited<ReturnType<typeof runSweep>>
