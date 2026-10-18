import type { ActOut, BookGraph, ChoiceOut, NodeOut } from '@/api/types'

export function act(id: string, position: number, extra: Partial<ActOut> = {}): ActOut {
  return {
    id,
    book_id: 'b1',
    key: id,
    position,
    title: `Act ${position + 1}`,
    color: null,
    summary: '',
    ...extra,
  }
}

export function choice(
  id: string,
  nodeId: string,
  target: string | null,
  extra: Partial<ChoiceOut> = {},
): ChoiceOut {
  return {
    id,
    node_id: nodeId,
    position: 0,
    label: `to ${target}`,
    kind: 'goto',
    condition: null,
    unmet_display: 'hide',
    print_text: null,
    min_tier: null,
    effects: [],
    dice: null,
    test: null,
    encounter_id: null,
    flee_allowed: false,
    outcomes: [
      {
        id: `${id}-o`,
        position: 0,
        key: 'default',
        target_node_id: target,
        range_lo: null,
        range_hi: null,
      },
    ],
    ...extra,
  }
}

export function node(
  id: string,
  actId: string,
  x: number,
  y: number,
  extra: Partial<NodeOut> = {},
): NodeOut {
  return {
    id,
    book_id: 'b1',
    act_id: actId,
    key: id,
    title: id.toUpperCase(),
    beat_notes: '',
    summary: '',
    is_act_entry: false,
    is_act_exit: false,
    ending_kind: null,
    ending_grade: null,
    ending_label: '',
    location_id: null,
    canonical_predecessor_id: null,
    style_override: {},
    section_pin: null,
    on_enter: [],
    is_shop: false,
    shop_sell_rate: null,
    x,
    y,
    collapsed: false,
    character_ids: [],
    variants: [{ id: `${id}-v`, position: 0, label: 'Default', condition: null, priority: 0 }],
    choices: [],
    encounters: [],
    items: [],
    shop_items: [],
    ...extra,
  }
}

export function graph(
  nodes: NodeOut[],
  acts: ActOut[] = [act('a1', 0)],
  start = nodes[0]?.id ?? null,
): BookGraph {
  return {
    book: {
      id: 'b1',
      series_id: 's1',
      key: 'book',
      number: 1,
      title: 'Book',
      synopsis: '',
      style_overrides: {},
      start_node_id: start,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    acts,
    nodes,
  }
}
