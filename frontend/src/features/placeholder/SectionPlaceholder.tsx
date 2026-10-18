import type { Section } from '@/app/sections'

/** Stand-in page for sections whose phase hasn't been built yet. */
export function SectionPlaceholder({ section }: { section: Section }) {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-6 py-20 text-center">
      <div className="mb-5 grid size-14 place-items-center rounded-2xl bg-accent/12 text-accent">
        <section.icon className="size-7" aria-hidden />
      </div>
      <h1 className="text-2xl font-semibold tracking-tight">{section.label}</h1>
      <p className="mt-2 text-muted">{section.summary}</p>
      <p className="mt-6 rounded-full border border-border px-3 py-1 text-xs font-medium text-muted">
        Arrives in Phase {section.phase}
      </p>
      <ul className="mt-6 space-y-1.5 text-left text-muted">
        {section.upcoming.map((u) => (
          <li key={u} className="flex gap-2">
            <span aria-hidden className="text-accent">
              •
            </span>
            {u}
          </li>
        ))}
      </ul>
    </div>
  )
}
