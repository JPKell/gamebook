import { Link } from 'react-router'

import { segments } from './mentions'
import { useMentionTargets } from './useMentionTargets'

/** Read-only text with paragraphs and [[mentions]] as links (broken ones flagged). */
export function MentionText({
  text,
  seriesId,
  className,
}: {
  text: string
  seriesId: string
  className?: string
}) {
  const targets = useMentionTargets(seriesId)
  const paragraphs = text.split(/\n{2,}/).filter((p) => p.trim())
  if (!paragraphs.length) return null
  return (
    <div className={className}>
      {paragraphs.map((p, i) => (
        <p key={i} className="mb-2 whitespace-pre-wrap last:mb-0">
          {segments(p, targets).map((s, j) =>
            'text' in s ? (
              <span key={j}>{s.text}</span>
            ) : s.target ? (
              <Link
                key={j}
                to={`/lore/${seriesId}?tab=${s.target.kind === 'character' ? 'characters' : 'entries'}&id=${s.target.id}`}
                className="font-medium text-accent hover:underline"
              >
                {s.label}
              </Link>
            ) : (
              <span
                key={j}
                title={`Nothing is called “${s.mention.slice(2, -2)}” yet`}
                className="text-danger underline decoration-dashed underline-offset-2"
              >
                {s.label}
              </span>
            ),
          )}
        </p>
      ))}
    </div>
  )
}
