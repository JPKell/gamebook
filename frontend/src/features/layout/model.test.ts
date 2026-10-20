import { describe, expect, it } from 'vitest'

import { DEFAULT_SETUP } from '@/features/art/api'

import {
  asLayout,
  effective,
  foldedPage,
  layoutBody,
  LINE_PRESETS,
  matchSize,
  mirrored,
  overrides,
  paddedCount,
  type Role,
  setStyle,
} from './model'

const role: Role = {
  key: 'section',
  label: 'Section numbers',
  description: '',
  default: { size_pt: 15, bold: true, align: 'center' },
}

describe('layout model', () => {
  it('fills in the layout parts an older setup lacks', () => {
    const l = asLayout(DEFAULT_SETUP)
    expect(l.header.verso).toEqual({ left: 'none', center: 'none', right: 'none' })
    expect(l.imposition).toMatchObject({ fold: false, signature_pages: 0, fold_marks: true })
    expect(l.title_page.show_series).toBe(true)
  })

  it('saves without the computed fields', () => {
    const body = layoutBody(asLayout(DEFAULT_SETUP))
    expect(body).not.toHaveProperty('text_width')
    expect(body).not.toHaveProperty('roles')
    expect(body).toHaveProperty('gutter_mm', 0)
  })

  it('sets and clears style overrides', () => {
    let styles = setStyle({}, 'section', 'size_pt', 20)
    styles = setStyle(styles, 'section', 'italic', true)
    expect(styles).toEqual({ section: { size_pt: 20, italic: true } })
    expect(overrides(styles, 'section').sort()).toEqual(['italic', 'size_pt'])
    expect(effective(styles, role)).toMatchObject({ size_pt: 20, italic: true, bold: true })
    // false is an override too (bold off), unlike null.
    styles = setStyle(styles, 'section', 'bold', false)
    expect(effective(styles, role).bold).toBe(false)
    styles = setStyle(styles, 'section', 'size_pt', null)
    styles = setStyle(styles, 'section', 'italic', null)
    styles = setStyle(styles, 'section', 'bold', null)
    expect(styles).toEqual({})
  })

  it('ignores the nulls the API sends for unset fields', () => {
    const fromApi = { section: { size_pt: null, italic: true, font: null } }
    expect(overrides(fromApi, 'section')).toEqual(['italic'])
    expect(effective(fromApi, role).size_pt).toBe(15)
    expect(setStyle(fromApi, 'section', 'italic', null)).toEqual({})
  })

  it('matches page sizes in either orientation', () => {
    expect(matchSize(210, 297)).toBe('a4')
    expect(matchSize(297, 210)).toBe('a4')
    expect(matchSize(152.4, 228.6)).toBe('trade6x9')
    expect(matchSize(100, 100)).toBeNull()
  })

  it('folds a sheet across its long side', () => {
    expect(foldedPage(279.4, 215.9)).toEqual({ w: 139.7, h: 215.9 })
    expect(foldedPage(210, 297)).toEqual({ w: 148.5, h: 210 })
  })

  it('pads to whole signatures', () => {
    const imp = asLayout(DEFAULT_SETUP).imposition
    expect(paddedCount(10, imp)).toBe(10)
    expect(paddedCount(10, { ...imp, fold: true })).toBe(12)
    expect(paddedCount(10, { ...imp, signature_pages: 8 })).toBe(16)
  })

  it('mirrors a left page for the right', () => {
    expect(mirrored({ left: 'page', center: 'title', right: 'none' })).toEqual({
      left: 'none',
      center: 'title',
      right: 'page',
    })
    // Page numbers outside: the right page's is the left page's, mirrored.
    const outside = LINE_PRESETS.find((p) => p.key === 'page_outside')!.line
    expect(mirrored(outside.verso)).toEqual(outside.recto)
  })
})
