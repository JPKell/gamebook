import { DropdownMenu as M } from 'radix-ui'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export function Menu({
  trigger,
  children,
  align = 'end',
}: {
  trigger: ReactNode
  children: ReactNode
  align?: 'start' | 'end'
}) {
  return (
    <M.Root>
      <M.Trigger asChild>{trigger}</M.Trigger>
      <M.Portal>
        <M.Content
          align={align}
          sideOffset={6}
          className="z-50 min-w-48 rounded-lg border border-border bg-surface p-1 shadow-xl"
        >
          {children}
        </M.Content>
      </M.Portal>
    </M.Root>
  )
}

export function MenuItem({
  children,
  onSelect,
  danger,
  disabled,
  icon,
}: {
  children: ReactNode
  onSelect: () => void
  danger?: boolean
  disabled?: boolean
  icon?: ReactNode
}) {
  return (
    <M.Item
      disabled={disabled}
      onSelect={onSelect}
      className={cn(
        'flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-surface-2 [&_svg]:size-4 [&_svg]:text-muted',
        danger && 'text-danger [&_svg]:text-danger',
      )}
    >
      {icon}
      {children}
    </M.Item>
  )
}

export function MenuSeparator() {
  return <M.Separator className="my-1 h-px bg-border" />
}
