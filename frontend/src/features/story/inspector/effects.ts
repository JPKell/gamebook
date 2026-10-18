import type { Effect, NodeUpdate } from '@/api/types'

export type EffectIn = NonNullable<NodeUpdate['on_enter']>[number]

/** API effects carry explicit nulls; strip them for writes. */
export function toInput(e: Effect): EffectIn {
  return Object.fromEntries(Object.entries(e).filter(([, v]) => v !== null)) as EffectIn
}
