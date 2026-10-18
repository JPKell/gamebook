import { Tooltip } from 'radix-ui'
import { NavLink } from 'react-router'

import { cn } from '@/lib/utils'

import { SECTIONS } from './sections'

export function NavRail() {
  return (
    <nav
      aria-label="Primary"
      className="row-span-3 flex w-14 flex-col items-center gap-1 border-r border-border bg-surface py-2"
    >
      <div className="mb-2 grid size-9 place-items-center" aria-hidden>
        <img src="/favicon.svg" alt="" className="size-7" />
      </div>
      <Tooltip.Provider delayDuration={300}>
        {SECTIONS.map((s) => (
          <Tooltip.Root key={s.id}>
            <Tooltip.Trigger asChild>
              <NavLink
                to={s.path}
                aria-label={s.label}
                className={({ isActive }) =>
                  cn(
                    'grid size-10 place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-text',
                    isActive && 'bg-accent/12 text-accent hover:bg-accent/15 hover:text-accent',
                    s.id === 'settings' && 'mt-auto',
                  )
                }
              >
                <s.icon className="size-5" aria-hidden />
              </NavLink>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content
                side="right"
                sideOffset={8}
                className="z-50 rounded-md bg-text px-2 py-1 text-xs text-bg shadow"
              >
                {s.label}
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>
        ))}
      </Tooltip.Provider>
    </nav>
  )
}
