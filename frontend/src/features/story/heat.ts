import { createContext, useContext } from 'react'

/** Playtest heat for the canvas: how many runs visited / died at each node. */
export interface Heat {
  batchId: string
  label: string
  runs: number
  visits: Record<string, number>
  deaths: Record<string, number>
}

export const HeatContext = createContext<Heat | null>(null)

export const useHeat = () => useContext(HeatContext)
