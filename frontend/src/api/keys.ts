/** TanStack Query keys. Book-scoped keys share the ['book', id] prefix so one
 * invalidation refreshes graph, problems and history together. */
export const qk = {
  health: ['health'] as const,
  seriesList: ['series'] as const,
  series: (id: string) => ['series', id] as const,
  book: (id: string) => ['book', id] as const,
  bookInfo: (id: string) => ['book', id, 'info'] as const,
  graph: (id: string) => ['book', id, 'graph'] as const,
  problems: (id: string) => ['book', id, 'problems'] as const,
  history: (id: string) => ['book', id, 'history'] as const,
  entities: (seriesId: string, kind: string) => ['entities', seriesId, kind] as const,
  ruleSystems: (seriesId: string) => ['entities', seriesId, 'rule-systems'] as const,
  flags: (seriesId: string) => ['entities', seriesId, 'flags'] as const,
  checkpoints: ['checkpoints'] as const,
}
