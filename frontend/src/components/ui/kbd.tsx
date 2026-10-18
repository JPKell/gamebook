import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        'rounded border border-border bg-surface-2 px-1.5 font-mono text-[10px] leading-4 text-muted',
        className,
      )}
    >
      {children}
    </kbd>
  )
}
