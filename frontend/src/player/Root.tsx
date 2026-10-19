import { Component, type ReactNode, useState } from 'react'

import { App } from './App'
import { checkBook, type PlayerBook } from './types'

/** The embedded book (export) or an error message; null in development. */
function embedded(): { book: PlayerBook } | { error: string } | null {
  if (!window.GAMEBOOK) return null
  try {
    return { book: checkBook(window.GAMEBOOK) }
  } catch (err) {
    return { error: err instanceof Error ? err.message : String(err) }
  }
}

/** Without an embedded book (development), open a book's data file. */
function Loader() {
  const [book, setBook] = useState<PlayerBook | null>(null)
  const [error, setError] = useState<string | null>(null)
  if (book) return <App book={book} />
  return (
    <main className="title">
      <h1>Gamebook player</h1>
      <p>
        No book is loaded. Export a web player from the app's Export page, or open a book file here.
      </p>
      <label className="card">
        Book file (book.js or .json)
        <input
          type="file"
          accept=".js,.json,application/json,text/javascript"
          onChange={async (e) => {
            const file = e.target.files?.[0]
            if (!file) return
            try {
              const text = (await file.text())
                .replace(/^\s*window\.GAMEBOOK\s*=\s*/, '')
                .replace(/;\s*$/, '')
              setBook(checkBook(JSON.parse(text)))
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err))
            }
          }}
        />
      </label>
      {error && <p role="alert">{error}</p>}
    </main>
  )
}

/** A crash shows a way back instead of a blank page (e.g. a save from an older edition). */
class Boundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null }
  static getDerivedStateFromError(e: unknown) {
    return { error: e instanceof Error ? e.message : String(e) }
  }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <main className="title">
        <p role="alert">Something went wrong: {this.state.error}</p>
        <button type="button" className="primary" onClick={() => this.setState({ error: null })}>
          Back to the start
        </button>
      </main>
    )
  }
}

export function Root() {
  const [found] = useState(embedded)
  if (found && 'book' in found)
    return (
      <Boundary>
        <App book={found.book} />
      </Boundary>
    )
  if (found)
    return (
      <main className="title">
        <p role="alert">{found.error}</p>
      </main>
    )
  return <Loader />
}
