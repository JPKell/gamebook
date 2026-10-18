import { CircleCheck, CircleHelp, CircleX } from 'lucide-react'

import type { components } from '@/api/schema'
import type { BookGraph, NodeOut } from '@/api/types'
import { cn } from '@/lib/utils'

import { useDigestTier, useNodeDigest, useOutline } from '../digest'
import { useStoryStore } from '../storyStore'

type Facts = components['schemas']['FactsOut']

const GROUPS: { key: keyof Facts; label: string }[] = [
  { key: 'flags', label: 'Codewords' },
  { key: 'items', label: 'Items' },
  { key: 'characters', label: 'Characters met' },
  { key: 'skills', label: 'Skills' },
]

function FactList({ facts, tone, empty }: { facts: Facts; tone: 'must' | 'may'; empty: string }) {
  const any = GROUPS.some((g) => facts[g.key]?.length)
  if (!any) return <p className="text-xs text-muted">{empty}</p>
  return (
    <dl className="space-y-1.5">
      {GROUPS.filter((g) => facts[g.key]?.length).map((g) => (
        <div key={g.key} className="flex flex-wrap items-baseline gap-1.5">
          <dt className="w-28 shrink-0 text-xs text-muted">{g.label}</dt>
          {facts[g.key]!.map((f) => (
            <dd
              key={f.key}
              title={f.key}
              className={cn(
                'rounded-full px-2 py-0.5 text-xs',
                tone === 'must'
                  ? 'bg-success/12 font-medium text-success'
                  : 'border border-dashed border-border text-muted',
              )}
            >
              {g.key === 'flags' ? <span className="font-mono">{f.label}</span> : f.label}
            </dd>
          ))}
        </div>
      ))}
    </dl>
  )
}

const VERDICT = {
  always: { icon: CircleCheck, label: 'Every reader can take it', className: 'text-success' },
  never: { icon: CircleX, label: 'No reader can take it', className: 'text-danger' },
  depends: { icon: CircleHelp, label: 'Depends on the route', className: 'text-muted' },
} as const

/** What a reader must / may have here, gate verdicts, depth, and outline beats. */
export function DigestTab({ graph, node }: { graph: BookGraph; node: NodeOut }) {
  const tier = useDigestTier(graph.book.series_id)
  const digest = useNodeDigest(graph.book.id, node.id, tier)
  const outline = useOutline(graph.book.id)
  const openNode = useStoryStore((s) => s.openNode)
  const d = digest.data
  if (digest.isError) return <p className="text-sm text-danger">{digest.error.message}</p>
  if (!d) return <p className="text-sm text-muted">Analysing…</p>
  const title = (id: string | null | undefined) => graph.nodes.find((n) => n.id === id)?.title
  const beats = (outline.data?.acts ?? []).flatMap((a) =>
    a.beats.filter((b) => b.node_ids.includes(node.id)).map((b) => ({ ...b, act: a.title })),
  )

  return (
    <div className="space-y-5 text-sm">
      {!d.reachable ? (
        <p role="status" className="rounded-lg border border-warning/40 bg-warning/8 p-3">
          No route from the start reaches this node, so nothing is known about the reader here.
        </p>
      ) : (
        <p className="text-muted">
          Reached after{' '}
          <span className="font-medium text-text">
            {d.depth_min === d.depth_max
              ? `${d.depth_min} choice${d.depth_min === 1 ? '' : 's'}`
              : `${d.depth_min}–${d.depth_max ?? '∞'} choices`}
          </span>
          {d.depth_max === null && ' (a loop allows longer routes)'}.
        </p>
      )}
      <section aria-label="Every reader has" className="space-y-2">
        <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">
          Every reader has
        </h3>
        <FactList facts={d.must} tone="must" empty="Nothing guaranteed." />
      </section>
      <section aria-label="Some readers have" className="space-y-2">
        <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">
          Some readers have
        </h3>
        <FactList facts={d.may} tone="may" empty="Nothing that depends on the route." />
        <p className="text-xs text-muted">
          Prose here shouldn't assume these. Item counts and stat values aren't tracked.
        </p>
      </section>
      {d.gates.length > 0 && (
        <section aria-label="Gated choices" className="space-y-2">
          <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">
            Gated choices
          </h3>
          <ul className="space-y-1">
            {d.gates.map((g) => {
              const v = VERDICT[g.verdict]
              return (
                <li key={g.choice_id} className="flex items-start gap-2">
                  <v.icon className={cn('mt-0.5 size-4 shrink-0', v.className)} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <button
                      type="button"
                      onClick={() => openNode(node.id, 'choices', g.choice_id)}
                      className="font-medium hover:underline"
                    >
                      {g.label || '(unlabelled choice)'}
                    </button>{' '}
                    <code className="text-xs text-muted">{g.condition}</code>
                    <span className={cn('block text-xs', v.className)}>{v.label}</span>
                  </span>
                </li>
              )
            })}
          </ul>
        </section>
      )}
      <section aria-label="Story so far" className="space-y-1">
        <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">Story so far</h3>
        {d.canonical_predecessor ? (
          <p>
            Continues from{' '}
            <button
              type="button"
              className="font-medium text-accent hover:underline"
              onClick={() => d.canonical_predecessor && openNode(d.canonical_predecessor)}
            >
              {title(d.canonical_predecessor)}
            </button>{' '}
            <span className="text-muted">
              (
              {d.canonical_predecessor_override
                ? 'chosen in the Lore tab'
                : 'automatic: shortest route'}
              )
            </span>
          </p>
        ) : (
          <p className="text-muted">This is where the story starts.</p>
        )}
      </section>
      <section aria-label="Story beats" className="space-y-1">
        <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">Story beats</h3>
        {beats.length ? (
          <ul className="list-disc pl-5">
            {beats.map((b) => (
              <li key={b.id}>
                {b.title} <span className="text-muted">· {b.act}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted">
            Not part of any beat. Plan beats under Lore → Outline.
          </p>
        )}
      </section>
    </div>
  )
}
