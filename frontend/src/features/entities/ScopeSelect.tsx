import { useSeries } from '@/api/queries'
import { Select } from '@/components/ui/inputs'

const SHARED = '__shared__'

/** Shared across the series, or limited to one book. */
export function ScopeSelect({
  seriesId,
  value,
  onChange,
  id,
}: {
  seriesId: string
  value: string | null
  onChange: (bookId: string | null) => void
  id?: string
}) {
  const series = useSeries(seriesId)
  return (
    <Select
      id={id}
      value={value ?? SHARED}
      onValueChange={(v) => onChange(v === SHARED || v === null ? null : v)}
      options={[
        { value: SHARED, label: 'Shared by every book' },
        ...(series.data?.books ?? []).map((b) => ({ value: b.id, label: `Only in ${b.title}` })),
      ]}
    />
  )
}
