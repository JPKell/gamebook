import type { components } from '@/api/schema'

import { useEntityProblems } from './api'

export type Problem = components['schemas']['ProblemOut']

/** Entity problems for a series, grouped by entity id. */
export function useProblemsById(seriesId: string) {
  const q = useEntityProblems(seriesId)
  const byId = new Map<string, Problem[]>()
  for (const p of q.data?.problems ?? [])
    if (p.entity_id) byId.set(p.entity_id, [...(byId.get(p.entity_id) ?? []), p])
  return byId
}

export function counts(problems: Problem[] | undefined) {
  return {
    errors: problems?.filter((p) => p.severity === 'error').length ?? 0,
    warnings: problems?.filter((p) => p.severity === 'warning').length ?? 0,
  }
}
