import { cn } from '@/lib/utils'

import type { Placement } from './api'

const TONE: Record<string, string> = {
  good: 'bg-success/15 text-success',
  low: 'bg-warning/15 text-warning',
  poor: 'bg-danger/15 text-danger',
  none: 'bg-surface-2 text-muted',
}
const WORD: Record<string, string> = {
  good: 'print-ready',
  low: 'soft in print',
  poor: 'too low for print',
}

/** Effective DPI at the printed size: green ≥ 300, amber ≥ 150, red below. */
export function DpiBadge({
  size,
  className,
}: {
  size: Placement['print_size']
  className?: string
}) {
  const label =
    size.status === 'none'
      ? 'Placeholder'
      : `${Math.round(size.dpi ?? 0)} dpi · ${WORD[size.status]}`
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums',
        TONE[size.status],
        className,
      )}
      title={`Prints at ${size.width_mm} × ${size.height_mm} mm`}
    >
      {label}
    </span>
  )
}
