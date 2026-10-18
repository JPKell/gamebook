import { Tabs as T } from 'radix-ui'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export function Tabs({
  value,
  onValueChange,
  tabs,
  className,
}: {
  value: string
  onValueChange: (value: string) => void
  tabs: { value: string; label: ReactNode; content: ReactNode; badge?: number }[]
  className?: string
}) {
  return (
    <T.Root
      value={value}
      onValueChange={onValueChange}
      className={cn('flex min-h-0 flex-col', className)}
    >
      <T.List className="flex shrink-0 gap-1 overflow-x-auto border-b border-border px-2">
        {tabs.map((t) => (
          <T.Trigger
            key={t.value}
            value={t.value}
            className="relative flex items-center gap-1.5 px-2.5 py-2 text-xs font-medium whitespace-nowrap text-muted transition-colors hover:text-text data-[state=active]:text-accent data-[state=active]:after:absolute data-[state=active]:after:inset-x-1 data-[state=active]:after:-bottom-px data-[state=active]:after:h-0.5 data-[state=active]:after:rounded data-[state=active]:after:bg-accent"
          >
            {t.label}
            {t.badge ? (
              <span className="rounded-full bg-surface-2 px-1.5 text-[10px] text-muted">
                {t.badge}
              </span>
            ) : null}
          </T.Trigger>
        ))}
      </T.List>
      {tabs.map((t) => (
        <T.Content
          key={t.value}
          value={t.value}
          className="min-h-0 flex-1 overflow-auto p-4 focus:outline-none"
        >
          {t.content}
        </T.Content>
      ))}
    </T.Root>
  )
}
