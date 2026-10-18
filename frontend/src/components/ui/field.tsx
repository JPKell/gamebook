import { type ReactNode, useId } from 'react'

import { cn } from '@/lib/utils'

/** Label + control + optional hint/error. Children receive the generated id. */
export function Field({
  label,
  hint,
  error,
  children,
  className,
  inline = false,
}: {
  label: ReactNode
  hint?: ReactNode
  error?: ReactNode
  children: (id: string) => ReactNode
  className?: string
  inline?: boolean
}) {
  const id = useId()
  return (
    <div className={cn(inline ? 'flex items-center gap-2' : 'space-y-1', className)}>
      <label htmlFor={id} className="block text-xs font-medium text-muted">
        {label}
      </label>
      {children(id)}
      {error ? (
        <p className="text-xs text-danger">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted">{hint}</p>
      ) : null}
    </div>
  )
}

export const controlClass =
  'w-full rounded-md border border-border bg-bg px-2.5 py-1.5 text-sm text-text placeholder:text-muted/70 focus:border-accent focus:outline-none disabled:opacity-60'
