import { useEffect, useMemo, useRef, useState } from 'react'

import type { Action, Game, GameEvent } from '@/engine/game'
import { enemyName, namesFor, narrate } from '@/engine/narrate'
import { effectiveTier, progressionEnabled } from '@/engine/rules'

import {
  AUTOSAVE,
  deleteSlot,
  loadSlots,
  type Move,
  newSeed,
  saveSlot,
  type Session,
  type Slot,
} from './saves'
import { metSoFar } from './met'
import type { PlayerBook } from './types'
import { open, useGame } from './useGame'

const ENDINGS: Record<string, string> = {
  victory: 'Victory!',
  death: 'Your adventure ends here.',
  defeated: 'You have been defeated.',
  dead_end: 'The road ends here.',
  stuck: 'You can go no further.',
}

export function App({ book }: { book: PlayerBook }) {
  const [session, setSession] = useState<Session | null>(null)
  const [slots, setSlots] = useState<Slot[]>(() => loadSlots(book.book_id))
  const [notice, setNotice] = useState<string | null>(null)
  const played = useGame(book, session)
  const where = played?.game.node?.title ?? ''
  // Autosave only after a move, so starting or loading never replaces the last autosave.
  const moved = useRef(false)

  const start = (s: Session) => {
    const opened = open(book, s)
    if ('error' in opened) {
      setNotice(`This save can't be opened with this edition of the book (${opened.error}).`)
      return
    }
    moved.current = false
    setNotice(
      opened.trimmed
        ? 'The book has changed since this save; it continues from the last move that still applies.'
        : null,
    )
    setSession(opened.session)
  }

  // Autosave after every move, so closing the tab never loses progress.
  useEffect(() => {
    if (!session || !moved.current) return
    saveSlot(book.book_id, {
      ...session,
      id: AUTOSAVE,
      name: 'Autosave',
      savedAt: new Date().toISOString(),
      where,
    })
  }, [book.book_id, session, where])

  useEffect(() => {
    document.title = book.title
  }, [book.title])

  if (!session || !played)
    return (
      <TitleScreen
        book={book}
        slots={slots}
        notice={notice}
        onStart={start}
        onDelete={(id) => {
          deleteSlot(book.book_id, id)
          setSlots(loadSlots(book.book_id))
        }}
      />
    )
  return (
    <PlayScreen
      book={book}
      session={session}
      game={played.game}
      latest={played.latest}
      notice={notice}
      onMove={(m) => {
        moved.current = true
        setNotice(null)
        setSession({ ...session, moves: [...session.moves, m] })
      }}
      onBack={() => {
        moved.current = true
        setSession({ ...session, moves: session.moves.slice(0, -1) })
      }}
      onSave={(name) => {
        const ok = saveSlot(book.book_id, {
          ...session,
          id: `slot-${Date.now()}`,
          name,
          savedAt: new Date().toISOString(),
          where,
        })
        setSlots(loadSlots(book.book_id))
        return ok
      }}
      onMenu={() => {
        setSlots(loadSlots(book.book_id)) // the autosave changed while playing
        setSession(null)
      }}
      onRestart={() => start({ ...session, seed: newSeed(), moves: [] })}
    />
  )
}

// ── title ─────────────────────────────────────────────────────────────────

function TitleScreen({
  book,
  slots,
  notice,
  onStart,
  onDelete,
}: {
  book: PlayerBook
  slots: Slot[]
  notice: string | null
  onStart: (s: Session) => void
  onDelete: (id: string) => void
}) {
  const [tier, setTier] = useState(book.tiers[0]?.key ?? '')
  const classes = useMemo(() => {
    const rules = book.bundle.book.rules
    return rules && tier ? [...effectiveTier(rules.tiers, tier).classes.values()] : []
  }, [book, tier])
  const [cls, setCls] = useState<string | null>(null)
  const chosen = classes.find((c) => c.key === cls) ?? classes[0] ?? null
  return (
    <main className="title">
      {book.cover && <img className="cover" src={book.cover.file} alt={book.cover.alt} />}
      <h1>{book.title}</h1>
      {book.series_title && <p className="series">{book.series_title}</p>}
      {notice && (
        <p role="alert" className="card">
          {notice}
        </p>
      )}
      <section className="card" aria-label="New adventure">
        {book.tiers.length > 1 && (
          <label>
            Edition
            <select value={tier} onChange={(e) => setTier(e.target.value)}>
              {book.tiers.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
        )}
        {classes.length > 0 && (
          <fieldset>
            <legend>Who are you?</legend>
            {classes.map((c) => (
              <label key={c.key} className="option">
                <input
                  type="radio"
                  name="class"
                  checked={chosen?.key === c.key}
                  onChange={() => setCls(c.key)}
                />
                <span>
                  <strong>{c.label}</strong>
                  {c.description && <span className="muted"> — {c.description}</span>}
                </span>
              </label>
            ))}
          </fieldset>
        )}
        <button
          type="button"
          className="primary"
          onClick={() =>
            onStart({ tier, seed: newSeed(), characterClass: chosen?.key ?? null, moves: [] })
          }
        >
          Begin a new adventure
        </button>
      </section>
      {slots.length > 0 && (
        <section className="card" aria-label="Saved games">
          <h2>Saved games</h2>
          <ul className="slots">
            {slots.map((s) => (
              <li key={s.id}>
                <button type="button" onClick={() => onStart(s)} className="slot">
                  <strong>{s.name}</strong>
                  <span className="muted">
                    {s.where || 'Start'} · {new Date(s.savedAt).toLocaleString()}
                  </span>
                </button>
                <button
                  type="button"
                  className="ghost"
                  aria-label={`Delete ${s.name}`}
                  onClick={() => onDelete(s.id)}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  )
}

// ── play ──────────────────────────────────────────────────────────────────

function PlayScreen({
  book,
  session,
  game,
  latest,
  notice,
  onMove,
  onBack,
  onSave,
  onMenu,
  onRestart,
}: {
  book: PlayerBook
  session: Session
  game: Game
  latest: GameEvent[]
  notice: string | null
  onMove: (m: Move) => void
  onBack: () => void
  onSave: (name: string) => boolean
  onMenu: () => void
  onRestart: () => void
}) {
  const names = useMemo(() => namesFor(game), [game])
  const s = game.state
  const node = game.node
  const top = useRef<HTMLDivElement>(null)
  const [saved, setSaved] = useState<string | null>(null)
  useEffect(() => {
    if (!saved) return
    const t = setTimeout(() => setSaved(null), 2500)
    return () => clearTimeout(t)
  }, [saved])
  useEffect(() => {
    top.current?.scrollIntoView({ block: 'start' })
    top.current?.focus({ preventScroll: true })
  }, [session.moves.length])
  // Readers see what happened, not dice workings, setup or authoring errors.
  const lines = latest
    .filter((e) => e.type !== 'error' && e.type !== 'character_created' && e.type !== 'roll')
    .map((e) => narrate(e, names))
    .filter((l): l is string => !!l)
  const art = (node ? (book.art[node.id] ?? []) : []).filter(
    (a) => (!a.variant_id || a.variant_id === s.variant_id) && (!a.tier || a.tier === s.tier),
  )
  const text = s.variant_id ? book.text[s.variant_id] : undefined
  const draft = !text && node ? book.notes[node.id] : undefined
  const actions = game.actions()
  const choices = actions.filter(
    (a) => a.type === 'choose' || a.type === 'attack' || a.type === 'flee',
  )
  const extras = actions.filter((a) => !choices.includes(a))
  const act = (a: Action) => onMove({ type: a.type, target: a.target })

  return (
    <div className="play">
      <header className="bar">
        <button type="button" className="ghost" onClick={onMenu}>
          ☰ Menu
        </button>
        <span className="bar-title">{book.title}</span>
        <button type="button" className="ghost" onClick={onBack} disabled={!session.moves.length}>
          ↶ Back
        </button>
        <button
          type="button"
          className="ghost"
          onClick={() => {
            const name = window.prompt('Name this save', node?.title ?? 'Saved game')
            if (name !== null)
              setSaved(
                onSave(name || 'Saved game')
                  ? 'Saved.'
                  : "Couldn't save (storage is full or blocked).",
              )
          }}
        >
          Save
        </button>
      </header>
      {saved && (
        <p role="status" className="toast">
          {saved}
        </p>
      )}
      <div className="layout">
        <main ref={top} tabIndex={-1} className="scene" aria-label="Story">
          {notice && <p className="card small">{notice}</p>}
          {art.map((a, i) => (
            <Figure key={i} art={a} />
          ))}
          {text ? (
            <div className="prose">
              {text
                .split(/\n{2,}/)
                .filter((p) => p.trim())
                .map((p, i) => (
                  <p key={i}>{p}</p>
                ))}
            </div>
          ) : draft ? (
            <div className="prose draft">
              <p className="muted small">
                This section hasn't been written yet; the author's notes:
              </p>
              <p>{draft}</p>
            </div>
          ) : null}
          {/* Always mounted, so screen readers announce each move's changes. */}
          <section
            aria-label="What happened"
            aria-live="polite"
            className={lines.length ? 'happened' : 'sr-only'}
          >
            {lines.map((l, i) => (
              <p key={`${session.moves.length}:${i}`}>{l}</p>
            ))}
          </section>
          {s.combat && (
            <section aria-label="Combat" className="combat">
              <h2>Combat — round {s.combat.round + 1}</h2>
              <table>
                <tbody>
                  {s.combat.enemies.map((e) => (
                    <tr key={e.key}>
                      <th scope="row">{enemyName(names, e.key)}</th>
                      {Object.entries(e.stats).map(([k, v]) => (
                        <td key={k}>
                          {names.stats[k] ?? k} {v}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
          {s.ended ? (
            <section aria-label="The end" className="ending">
              <p className={`ending-${s.ended}`}>{ENDINGS[s.ended] ?? 'The end.'}</p>
              <button type="button" className="primary" onClick={onRestart}>
                Play again
              </button>
              <button
                type="button"
                className="ghost"
                onClick={onBack}
                disabled={!session.moves.length}
              >
                Go back a step
              </button>
            </section>
          ) : (
            <nav aria-label="Choices" className="choices">
              {choices.map((a) => (
                <button
                  key={`${a.type}:${a.target}`}
                  type="button"
                  disabled={!a.enabled}
                  title={a.reason ?? undefined}
                  onClick={() => act(a)}
                >
                  {a.label || 'Continue'}
                  {a.reason && <span className="muted small"> ({a.reason})</span>}
                </button>
              ))}
              {extras.length > 0 && (
                <div className="extras" role="group" aria-label="Items and shop">
                  {extras.map((a) => (
                    <button
                      key={`${a.type}:${a.target}`}
                      type="button"
                      className="small"
                      disabled={!a.enabled}
                      title={a.reason ?? undefined}
                      onClick={() => act(a)}
                    >
                      {a.label}
                      {a.reason && ` (${a.reason})`}
                    </button>
                  ))}
                </div>
              )}
            </nav>
          )}
        </main>
        <aside className="side">
          <Sheet game={game} names={names} />
          <Maps book={book} game={game} />
          <Codex book={book} game={game} />
        </aside>
      </div>
    </div>
  )
}

function Figure({ art }: { art: PlayerBook['art'][string][number] }) {
  const [big, setBig] = useState(false)
  const close = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (!big) return
    close.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setBig(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [big])
  const img = <img src={art.file} alt={art.alt} className={`art art-${art.display}`} />
  return (
    <figure className={`figure figure-${art.display}`}>
      {art.zoom ? (
        <button
          type="button"
          className="plain"
          onClick={() => setBig(true)}
          aria-label={`Enlarge: ${art.alt || 'illustration'}`}
        >
          {img}
        </button>
      ) : (
        img
      )}
      {art.caption && <figcaption>{art.caption}</figcaption>}
      {big && (
        <button
          ref={close}
          type="button"
          className="lightbox"
          onClick={() => setBig(false)}
          aria-label="Close the enlarged image"
        >
          <img src={art.file} alt="" />
        </button>
      )}
    </figure>
  )
}

function Sheet({ game, names }: { game: Game; names: ReturnType<typeof namesFor> }) {
  const s = game.state
  const eff = game.peekStats() // display only: never logs into the game
  const items = [...s.items].filter(([, n]) => n > 0).sort(([a], [b]) => (a < b ? -1 : 1))
  const equipped = new Set(s.equipped.values())
  const cls = s.character_class ? game.tier.classes.get(s.character_class)?.label : null
  const pr = game.tier.progression
  const levels =
    progressionEnabled(pr) &&
    game.tier.stats.has(pr.xp_stat!) &&
    game.tier.stats.has(pr.level_stat!)
  const need = levels ? game.xpNeeded() : null
  const money = game.currency
  return (
    <section aria-label="Adventure sheet" className="card">
      <h2>Adventure sheet</h2>
      {cls && <p className="muted">{cls}</p>}
      {(money || levels) && (
        <p className="sheet-headline">
          {money && (
            <span>
              {game.tier.stats.get(money)?.label ?? money}: <strong>{eff[money] ?? 0}</strong>
            </span>
          )}
          {levels && (
            <span>
              {game.tier.stats.get(pr.level_stat!)?.label ?? pr.level_stat}{' '}
              <strong>{s.stats.get(pr.level_stat!) ?? 0}</strong>
              {' · '}
              {s.stats.get(pr.xp_stat!) ?? 0}
              {need !== null ? ` / ${need}` : ''} {game.tier.stats.get(pr.xp_stat!)?.label ?? 'XP'}
            </span>
          )}
        </p>
      )}
      <dl className="stats">
        {[...game.tier.stats]
          .filter(([, sd]) => sd.applies_to.includes('player'))
          .map(([k, sd]) => {
            const base = s.stats.get(k) ?? 0
            const shown = eff[k] ?? base
            const max = s.max_stats.get(k)
            return (
              <div key={k}>
                <dt>{sd.label}</dt>
                <dd>
                  {shown}
                  {shown !== base && <span className="muted small"> ({base})</span>}
                  {max !== undefined && <span className="muted small"> / {max}</span>}
                </dd>
              </div>
            )
          })}
      </dl>
      <h3>Items</h3>
      {items.length ? (
        <ul className="list">
          {items.map(([k, n]) => (
            <li key={k}>
              {names.items[k] ?? k}
              {n > 1 && ` ×${n}`}
              {equipped.has(k) && <span className="muted small"> (equipped)</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted small">Nothing yet.</p>
      )}
      {s.skills.size > 0 && (
        <>
          <h3>Skills</h3>
          <p>{[...s.skills].map((k) => names.skills[k] ?? k).join(', ')}</p>
        </>
      )}
      {s.flags.size > 0 && (
        <>
          <h3>Codewords</h3>
          <p className="codewords">{[...s.flags].sort().join(' · ')}</p>
        </>
      )}
    </section>
  )
}

function Maps({ book, game }: { book: PlayerBook; game: Game }) {
  const [index, setIndex] = useState(0)
  if (!book.maps.length) return null
  const m = book.maps[Math.min(index, book.maps.length - 1)]!
  const markers = m.markers.filter((mk) => game.holds(mk.visible_if))
  return (
    <section aria-label="Map" className="card">
      <h2>
        {book.maps.length > 1 ? (
          <select
            aria-label="Choose a map"
            value={index}
            onChange={(e) => setIndex(Number(e.target.value))}
          >
            {book.maps.map((x, i) => (
              <option key={x.id} value={i}>
                {x.title}
              </option>
            ))}
          </select>
        ) : (
          m.title
        )}
      </h2>
      {m.file && (
        <div className="map">
          <img src={m.file} alt={m.alt} />
          {markers.map((mk) => (
            <span
              key={mk.id}
              aria-hidden
              className={mk.node_id && mk.node_id === game.state.node_id ? 'pin here' : 'pin'}
              style={{ left: `${mk.x * 100}%`, top: `${mk.y * 100}%` }}
              title={mk.label}
            />
          ))}
        </div>
      )}
      <ul className="list small" aria-label={`Places on ${m.title}`}>
        {markers.map((mk) => (
          <li key={mk.id} className={mk.node_id === game.state.node_id ? 'here-label' : ''}>
            {mk.label || 'Marked place'}
            {mk.node_id === game.state.node_id && ' (you are here)'}
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Codex pages; the bestiary and items show only what the reader has met. */
function Codex({ book, game }: { book: PlayerBook; game: Game }) {
  const pages = book.codex[game.state.tier] ?? []
  const [open, setOpen] = useState(false)
  const [pick, setPick] = useState(0)
  if (!pages.length) return null
  const page = pages[Math.min(pick, pages.length - 1)]!
  const met = metSoFar(game)
  // Unmet entries are hidden by CSS injected into the page (entries carry their key).
  const hide =
    '<style>[data-enemy],[data-item]{display:none}' +
    [...met.enemies]
      .map((k) => `[data-enemy="${cssEscape(k)}"]`)
      .concat([...met.items].map((k) => `[data-item="${cssEscape(k)}"]`))
      .map((sel) => `${sel}{display:flow-root}`)
      .join('') +
    '</style>'
  const doc = page.html.replace('</head>', () => `${hide}</head>`) // no $-patterns
  return (
    <section aria-label="Codex" className="card">
      <button
        type="button"
        className="plain heading"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        Codex {open ? '▾' : '▸'}
      </button>
      {open && (
        <>
          {pages.length > 1 && (
            <select
              aria-label="Codex page"
              value={pick}
              onChange={(e) => setPick(Number(e.target.value))}
            >
              {pages.map((p, i) => (
                <option key={p.id} value={i}>
                  {p.title}
                </option>
              ))}
            </select>
          )}
          <iframe title={page.title} srcDoc={doc} sandbox="" className="codex" />
        </>
      )}
    </section>
  )
}

/** Keys follow the key pattern, but escape anything that could end the selector or style. */
const cssEscape = (s: string) =>
  s.replace(/[^A-Za-z0-9_-]/g, (c) => `\\${c.codePointAt(0)!.toString(16)} `)
