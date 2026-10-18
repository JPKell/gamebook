import { Plus, Store, Swords, Trash2 } from 'lucide-react'

import {
  useCreateEncounter,
  useCreateEnemy,
  useCreateItem,
  useDeleteEncounter,
  useSetNodeItems,
  useSetShop,
  useUpdateEncounter,
} from '@/api/mutations'
import { useEntities } from '@/api/queries'
import type { BookGraph, EncounterIn, EncounterOut, NodeOut } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Checkbox, NumberInput, Select, TextInput } from '@/components/ui/inputs'

const NEW = '__new__'

function enemiesOf(e: EncounterOut) {
  return e.enemies.map((x) => ({ enemy_id: x.enemy_id, level: x.level, count: x.count }))
}

function encounterIn(e: EncounterOut): EncounterIn {
  return {
    label: e.label,
    mode: e.mode,
    fight: e.fight,
    table_id: e.table_id ?? null,
    enemies: enemiesOf(e),
  }
}

export function EncountersTab({ graph, node }: { graph: BookGraph; node: NodeOut }) {
  const bookId = graph.book.id
  const seriesId = graph.book.series_id
  const enemies = useEntities('enemies', seriesId, bookId)
  const tables = useEntities('tables', seriesId, bookId)
  const items = useEntities('items', seriesId, bookId)
  const createEncounter = useCreateEncounter(bookId)
  const updateEncounter = useUpdateEncounter(bookId)
  const deleteEncounter = useDeleteEncounter(bookId)
  const setItems = useSetNodeItems(bookId)
  const setShop = useSetShop(bookId)
  const newEnemy = useCreateEnemy(seriesId)
  const newItem = useCreateItem(seriesId)

  const enemyOptions = [
    ...(enemies.data ?? []).map((e) => ({ value: e.id, label: e.name })),
    { value: NEW, label: '+ New enemy…' },
  ]
  const itemOptions = [
    ...(items.data ?? []).map((i) => ({ value: i.id, label: i.name })),
    { value: NEW, label: '+ New item…' },
  ]

  /** Resolve the "+ New…" option by creating the entity first. */
  const pick = async (id: string | null, kind: 'enemy' | 'item'): Promise<string | null> => {
    if (id !== NEW) return id
    const name = window.prompt(kind === 'enemy' ? 'New enemy name' : 'New item name')?.trim()
    if (!name) return null
    const created = await (kind === 'enemy' ? newEnemy : newItem).mutateAsync({ name })
    return created.id
  }

  const saveEncounter = (e: EncounterOut, change: Partial<EncounterIn>) =>
    updateEncounter.mutate({ id: e.id, ...encounterIn(e), ...change })

  const placements = node.items.map((p) => ({ item_id: p.item_id, qty: p.qty }))
  const shopItems = node.shop_items.map((s) => ({
    item_id: s.item_id,
    price: s.price,
    stock: s.stock ?? null,
  }))
  const saveShop = (
    change: Partial<{ is_shop: boolean; sell_rate: number | null; items: typeof shopItems }>,
  ) =>
    setShop.mutate({
      nodeId: node.id,
      is_shop: node.is_shop,
      sell_rate: node.shop_sell_rate ?? null,
      items: shopItems,
      ...change,
    })

  return (
    <div className="space-y-6">
      <section className="space-y-3" aria-labelledby="enc-h">
        <h3 id="enc-h" className="flex items-center gap-1.5 text-sm font-semibold">
          <Swords className="size-4 text-muted" aria-hidden /> Encounters
        </h3>
        {node.encounters.length === 0 && <p className="text-xs text-muted">No enemies here.</p>}
        {node.encounters.map((e, i) => (
          <div key={e.id} className="space-y-2 rounded-lg border border-border p-3">
            <div className="flex items-center gap-2">
              <TextInput
                aria-label="Encounter name"
                value={e.label}
                placeholder={`Encounter ${i + 1}`}
                onCommit={(label) => saveEncounter(e, { label })}
              />
              <Button
                variant="ghost"
                size="icon"
                aria-label="Delete encounter"
                onClick={() => deleteEncounter.mutate(e.id)}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Select
                aria-label="Encounter type"
                value={e.mode}
                onValueChange={(mode) => mode && saveEncounter(e, { mode })}
                options={[
                  { value: 'fixed', label: 'Fixed enemies' },
                  { value: 'table', label: 'Random table' },
                ]}
              />
              <Select
                aria-label="Fight order"
                value={e.fight}
                onValueChange={(fight) => fight && saveEncounter(e, { fight })}
                options={[
                  { value: 'sequential', label: 'One at a time' },
                  { value: 'simultaneous', label: 'All at once' },
                ]}
              />
            </div>
            {e.mode === 'table' ? (
              <Select
                aria-label="Random table"
                value={e.table_id ?? null}
                placeholder="Choose a table…"
                onValueChange={(table_id) => saveEncounter(e, { table_id })}
                options={(tables.data ?? []).map((t) => ({
                  value: t.id,
                  label: `${t.name} (${t.dice})`,
                }))}
              />
            ) : (
              <div className="space-y-1.5">
                {e.enemies.map((x, j) => (
                  <div key={x.id} className="flex items-center gap-2">
                    <Select
                      aria-label="Enemy"
                      value={x.enemy_id}
                      onValueChange={async (v) => {
                        const id = await pick(v, 'enemy')
                        if (!id) return
                        const list = enemiesOf(e).map((y, k) =>
                          k === j ? { ...y, enemy_id: id } : y,
                        )
                        saveEncounter(e, { enemies: list })
                      }}
                      options={enemyOptions}
                      className="min-w-0 flex-1"
                    />
                    <label className="flex items-center gap-1 text-xs text-muted">
                      Lv
                      <NumberInput
                        aria-label="Level"
                        min={1}
                        value={x.level}
                        onCommit={(level) =>
                          saveEncounter(e, {
                            enemies: enemiesOf(e).map((y, k) =>
                              k === j ? { ...y, level: Math.max(1, level ?? 1) } : y,
                            ),
                          })
                        }
                        className="w-14 px-1.5"
                      />
                    </label>
                    <label className="flex items-center gap-1 text-xs text-muted">
                      ×
                      <NumberInput
                        aria-label="Count"
                        min={1}
                        value={x.count}
                        onCommit={(count) =>
                          saveEncounter(e, {
                            enemies: enemiesOf(e).map((y, k) =>
                              k === j ? { ...y, count: Math.max(1, count ?? 1) } : y,
                            ),
                          })
                        }
                        className="w-12 px-1.5"
                      />
                    </label>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Remove enemy"
                      onClick={() =>
                        saveEncounter(e, { enemies: enemiesOf(e).filter((_, k) => k !== j) })
                      }
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                ))}
                <Select
                  aria-label="Add enemy"
                  value={null}
                  placeholder="+ Add enemy…"
                  onValueChange={async (v) => {
                    const id = await pick(v, 'enemy')
                    if (id)
                      saveEncounter(e, {
                        enemies: [...enemiesOf(e), { enemy_id: id, level: 1, count: 1 }],
                      })
                  }}
                  options={enemyOptions}
                />
              </div>
            )}
          </div>
        ))}
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            createEncounter.mutate({
              nodeId: node.id,
              label: '',
              mode: 'fixed',
              fight: 'sequential',
              enemies: [],
            })
          }
        >
          <Plus className="size-4" /> Add encounter
        </Button>
      </section>

      <section className="space-y-2" aria-labelledby="items-h">
        <h3 id="items-h" className="text-sm font-semibold">
          Items found here
        </h3>
        <p className="text-xs text-muted">
          The reader may take these. Items given automatically belong in On entry effects.
        </p>
        {node.items.map((p, j) => (
          <div key={p.id} className="flex items-center gap-2">
            <Select
              aria-label="Item"
              value={p.item_id}
              onValueChange={async (v) => {
                const id = await pick(v, 'item')
                if (id)
                  setItems.mutate({
                    nodeId: node.id,
                    items: placements.map((x, k) => (k === j ? { ...x, item_id: id } : x)),
                  })
              }}
              options={itemOptions}
              className="min-w-0 flex-1"
            />
            <NumberInput
              aria-label="Quantity"
              min={1}
              value={p.qty}
              onCommit={(qty) =>
                setItems.mutate({
                  nodeId: node.id,
                  items: placements.map((x, k) =>
                    k === j ? { ...x, qty: Math.max(1, qty ?? 1) } : x,
                  ),
                })
              }
              className="w-16"
            />
            <Button
              variant="ghost"
              size="icon"
              aria-label="Remove item"
              onClick={() =>
                setItems.mutate({ nodeId: node.id, items: placements.filter((_, k) => k !== j) })
              }
            >
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        ))}
        <Select
          aria-label="Add item found here"
          value={null}
          placeholder="+ Add item…"
          onValueChange={async (v) => {
            const id = await pick(v, 'item')
            if (id)
              setItems.mutate({ nodeId: node.id, items: [...placements, { item_id: id, qty: 1 }] })
          }}
          options={itemOptions}
        />
      </section>

      <section className="space-y-2" aria-labelledby="shop-h">
        <h3 id="shop-h" className="flex items-center gap-1.5 text-sm font-semibold">
          <Store className="size-4 text-muted" aria-hidden /> Shop
        </h3>
        <Checkbox
          label="This node is a shop"
          checked={node.is_shop}
          onCheckedChange={(is_shop) => saveShop({ is_shop })}
        />
        {node.is_shop && (
          <div className="space-y-2">
            <Field label="Buys items back at (% of value)">
              {(id) => (
                <NumberInput
                  id={id}
                  allowEmpty
                  min={0}
                  max={100}
                  value={node.shop_sell_rate ?? null}
                  onCommit={(sell_rate) => saveShop({ sell_rate })}
                  className="w-24"
                />
              )}
            </Field>
            {node.shop_items.map((s, j) => (
              <div key={s.id} className="flex items-center gap-2">
                <Select
                  aria-label="Item for sale"
                  value={s.item_id}
                  onValueChange={async (v) => {
                    const id = await pick(v, 'item')
                    if (id)
                      saveShop({
                        items: shopItems.map((x, k) => (k === j ? { ...x, item_id: id } : x)),
                      })
                  }}
                  options={itemOptions}
                  className="min-w-0 flex-1"
                />
                <NumberInput
                  aria-label="Price"
                  min={0}
                  value={s.price}
                  onCommit={(price) =>
                    saveShop({
                      items: shopItems.map((x, k) => (k === j ? { ...x, price: price ?? 0 } : x)),
                    })
                  }
                  className="w-16"
                  title="Price"
                />
                <NumberInput
                  aria-label="Stock (empty = unlimited)"
                  allowEmpty
                  min={0}
                  value={s.stock ?? null}
                  placeholder="∞"
                  onCommit={(stock) =>
                    saveShop({ items: shopItems.map((x, k) => (k === j ? { ...x, stock } : x)) })
                  }
                  className="w-16"
                  title="Stock (empty = unlimited)"
                />
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Remove from shop"
                  onClick={() => saveShop({ items: shopItems.filter((_, k) => k !== j) })}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
            ))}
            <Select
              aria-label="Add item for sale"
              value={null}
              placeholder="+ Sell an item…"
              onValueChange={async (v) => {
                const id = await pick(v, 'item')
                if (id) saveShop({ items: [...shopItems, { item_id: id, price: 1, stock: null }] })
              }}
              options={itemOptions}
            />
          </div>
        )}
      </section>
    </div>
  )
}
