import { type ReactNode, Suspense } from 'react'

/** Suspense boundary for lazily loaded feature pages. */
export function Page({ children }: { children: ReactNode }) {
  return <Suspense fallback={<p className="p-6 text-muted">Loading…</p>}>{children}</Suspense>
}
