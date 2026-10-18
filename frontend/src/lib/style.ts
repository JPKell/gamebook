import type { StyleGuide } from '@/api/types'

export type FullStyle = Required<StyleGuide>

export const DEFAULT_STYLE: FullStyle = {
  pov: 'second',
  tense: 'present',
  word_min: 150,
  word_max: 400,
  voice: '',
  notes: '',
}

export function fullStyle(style: StyleGuide | undefined): FullStyle {
  return {
    ...DEFAULT_STYLE,
    ...Object.fromEntries(Object.entries(style ?? {}).filter(([, v]) => v != null)),
  }
}
