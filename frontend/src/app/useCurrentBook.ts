import { useMatch } from 'react-router'

/** The book open in the Story view, if any (from the URL). */
export function useCurrentBookId(): string | undefined {
  return useMatch('/story/:bookId')?.params.bookId
}
