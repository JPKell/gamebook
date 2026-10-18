import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { api, unwrap } from '@/api/client'
import { useApiMutation } from '@/api/queries'
import type { components } from '@/api/schema'

type S = components['schemas']
export type Provider = S['ProviderOut']
export type ProviderIn = S['ProviderIn']
export type ProviderUpdate = S['ProviderUpdate']
export type ModelInfo = S['ModelInfo']
export type Template = S['TemplateOut']
export type WritingSettings = S['WritingSettings']
export type Role = 'writer' | 'critic' | 'editor' | 'summarizer'
export const ROLES: { key: Role; label: string; hint: string }[] = [
  { key: 'writer', label: 'Writer', hint: 'Drafts the prose for a section.' },
  {
    key: 'critic',
    label: 'Critic',
    hint: 'Scores the draft against a rubric and lists issues (JSON).',
  },
  { key: 'editor', label: 'Editor', hint: 'Rewrites the draft to fix the critic’s issues.' },
  { key: 'summarizer', label: 'Summarizer', hint: 'Writes the 2–3 sentence “story so far” note.' },
]

const lk = {
  providers: ['llm', 'providers'] as const,
  templates: ['llm', 'templates'] as const,
  calls: (q: Record<string, unknown>) => ['llm', 'calls', q] as const,
  call: (id: string) => ['llm', 'call', id] as const,
  costs: (seriesId: string | null) => ['llm', 'costs', seriesId] as const,
  settings: (seriesId: string) => ['llm', 'settings', seriesId] as const,
}

export function useProviders() {
  return useQuery({ queryKey: lk.providers, queryFn: () => unwrap(api.GET('/api/llm/providers')) })
}

export function useCreateProvider() {
  return useApiMutation(
    (body: ProviderIn) => unwrap(api.POST('/api/llm/providers', { body })),
    () => [lk.providers],
  )
}

export function useUpdateProvider() {
  return useApiMutation(
    ({ id, ...body }: ProviderUpdate & { id: string }) =>
      unwrap(
        api.PATCH('/api/llm/providers/{provider_id}', {
          params: { path: { provider_id: id } },
          body,
        }),
      ),
    () => [lk.providers],
  )
}

export function useDeleteProvider() {
  return useApiMutation(
    (id: string) =>
      unwrap(
        api.DELETE('/api/llm/providers/{provider_id}', { params: { path: { provider_id: id } } }),
      ),
    () => [lk.providers],
  )
}

export function useTestProvider() {
  return useApiMutation(
    (id: string) =>
      unwrap(
        api.POST('/api/llm/providers/{provider_id}/test', {
          params: { path: { provider_id: id } },
        }),
      ),
    () => [],
  )
}

export function useTemplates() {
  return useQuery({ queryKey: lk.templates, queryFn: () => unwrap(api.GET('/api/llm/templates')) })
}

export function useSaveTemplate() {
  return useApiMutation(
    ({ role, ...body }: { role: Role; system: string; user: string; notes?: string }) =>
      unwrap(api.POST('/api/llm/templates/{role}', { params: { path: { role } }, body })),
    () => [lk.templates],
  )
}

export function useActivateTemplate() {
  return useApiMutation(
    (id: string) =>
      unwrap(
        api.POST('/api/llm/templates/{template_id}/activate', {
          params: { path: { template_id: id } },
        }),
      ),
    () => [lk.templates],
  )
}

export function usePreviewTemplate() {
  return useApiMutation(
    ({ role, ...body }: { role: Role; variant_id: string; system?: string; user?: string }) =>
      unwrap(api.POST('/api/llm/templates/{role}/preview', { params: { path: { role } }, body })),
    () => [],
  )
}

export function useCalls(query: {
  series_id?: string
  role?: string
  status?: string
  pipeline_run_id?: string
  node_id?: string
  offset: number
}) {
  return useQuery({
    queryKey: lk.calls(query),
    queryFn: () =>
      unwrap(api.GET('/api/llm/calls', { params: { query: { ...query, limit: 25 } } })),
    placeholderData: keepPreviousData,
    staleTime: 0,
  })
}

export function useCall(id: string | null) {
  return useQuery({
    queryKey: lk.call(id ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/llm/calls/{call_id}', { params: { path: { call_id: id! } } })),
    enabled: !!id,
  })
}

export function useCosts(seriesId: string | null) {
  return useQuery({
    queryKey: lk.costs(seriesId),
    queryFn: () =>
      unwrap(api.GET('/api/llm/costs', { params: { query: { series_id: seriesId } } })),
    staleTime: 0,
  })
}

export function useWritingSettings(seriesId: string | undefined) {
  return useQuery({
    queryKey: lk.settings(seriesId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/series/{series_id}/writing-settings', {
          params: { path: { series_id: seriesId! } },
        }),
      ),
    enabled: !!seriesId,
  })
}

export function useSaveWritingSettings(seriesId: string) {
  return useApiMutation(
    (body: WritingSettings) =>
      unwrap(
        api.PUT('/api/series/{series_id}/writing-settings', {
          params: { path: { series_id: seriesId } },
          body,
        }),
      ),
    () => [lk.settings(seriesId), ['writing']],
  )
}

/** Labelled presets for new providers. */
export const PRESETS: { label: string; body: ProviderIn }[] = [
  {
    label: 'Local server (llama.cpp, vLLM, Ollama…)',
    body: {
      name: 'Local',
      kind: 'openai',
      base_url: 'http://localhost:11434/v1',
      models: [],
      max_concurrency: 1,
    },
  },
  {
    label: 'OpenAI',
    body: {
      name: 'OpenAI',
      kind: 'openai',
      base_url: 'https://api.openai.com/v1',
      api_key_env: 'OPENAI_API_KEY',
      models: [],
      max_concurrency: 4,
    },
  },
  {
    label: 'OpenRouter',
    body: {
      name: 'OpenRouter',
      kind: 'openai',
      base_url: 'https://openrouter.ai/api/v1',
      api_key_env: 'OPENROUTER_API_KEY',
      models: [],
      max_concurrency: 4,
      headers: { 'X-Title': 'Gamebook Studio' },
    },
  },
  {
    label: 'Offline test model (no network, canned prose)',
    body: {
      name: 'Offline test model',
      kind: 'fake',
      models: [
        {
          id: 'offline',
          label: 'Offline',
          context_window: 8192,
          input_per_mtok: 0,
          output_per_mtok: 0,
        },
      ],
    },
  },
]
