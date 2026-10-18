import { QueryClient, QueryClientProvider, QueryObserver } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'

import { qk } from '@/api/keys'
import type { RuleSystemOut } from '@/api/types'

import { useSaveDefinition } from './api'
import type { RuleSystemDef } from './defs'

afterEach(() => vi.restoreAllMocks())

const tier = (label: string): RuleSystemDef => ({ tiers: [{ key: 'basic', label }] })
const row = (definition: RuleSystemDef) => ({
  id: 'rs',
  series_id: 's',
  key: 'k',
  name: 'n',
  is_active: true,
  definition: definition as RuleSystemOut['definition'],
  updated_at: '',
})

describe('useSaveDefinition', () => {
  it('never refetches between queued saves, and resyncs once at the end', async () => {
    let server = tier('Start')
    const held: (() => void)[] = []
    const log: string[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const req = input instanceof Request ? input : new Request(String(input))
      if (req.method === 'PATCH') {
        const { definition } = (await req.json()) as { definition: RuleSystemDef }
        await new Promise<void>((release) => held.push(release)) // released by the test
        server = definition
        log.push(`saved ${server.tiers[0]!.label}`)
        return Response.json(row(server))
      }
      log.push(`fetched ${server.tiers[0]!.label}`)
      return Response.json([row(server)])
    })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    qc.setQueryData<RuleSystemOut[]>(qk.ruleSystems('s'), [row(tier('Start'))])
    const observer = new QueryObserver(qc, {
      queryKey: qk.ruleSystems('s'),
      queryFn: async () => (await fetch(`${location.origin}/api/series/s/rule-systems`)).json(),
      staleTime: Infinity,
    })
    const unsubscribe = observer.subscribe(() => {})
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useSaveDefinition('s', 'rs'), { wrapper })
    const label = () =>
      (qc.getQueryData<RuleSystemOut[]>(qk.ruleSystems('s'))![0]!.definition as RuleSystemDef)
        .tiers[0]!.label

    act(() => result.current.mutate(tier('Start+A')))
    act(() => result.current.mutate(tier('Start+A+B')))
    await waitFor(() => expect(held).toHaveLength(1))
    act(() => held.shift()!()) // A lands; B is still queued
    await waitFor(() => expect(held).toHaveLength(1)) // B in flight
    await new Promise((r) => setTimeout(r, 20))
    // A refetch here would return "Start+A" and clobber B's optimistic state.
    expect(log).toEqual(['saved Start+A'])
    expect(label()).toBe('Start+A+B')
    act(() => held.shift()!())
    await waitFor(() =>
      expect(log).toEqual(['saved Start+A', 'saved Start+A+B', 'fetched Start+A+B']),
    )
    expect(label()).toBe('Start+A+B')
    unsubscribe()
  })
})
