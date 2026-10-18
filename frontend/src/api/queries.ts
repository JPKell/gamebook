import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from './client'

export const queryKeys = {
  health: ['health'] as const,
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => unwrap(api.GET('/api/health')),
    refetchInterval: 15_000,
    retry: false,
  })
}
