import { useCallback, useEffect, useRef } from 'react'

/**
 * Merge patches into the last value sent, not the (possibly stale) server copy, so two
 * quick edits to one object (e.g. size, then alignment) never undo each other. Follows
 * the server value again once nothing is in flight (mutations stay pending until their
 * refetch lands, so the server copy is current by then).
 */
export function useLatest<T extends object>(server: T, pending: boolean) {
  const sent = useRef(server)
  useEffect(() => {
    if (!pending) sent.current = server
  }, [server, pending])
  return useCallback((patch: Partial<T>): T => {
    sent.current = { ...sent.current, ...patch }
    return sent.current
  }, [])
}
