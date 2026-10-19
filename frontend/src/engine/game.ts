/**
 * The game engine: a faithful port of `core/engine/game.py`, `combat.py` and `env.py`.
 *
 * Same book, tier, seed, creation options and actions → the same events and final
 * state as the Python engine. The golden traces (`backend/tests/core/golden`) and
 * the parity corpus prove it in CI (`parity.test.ts`).
 */
import { type Env, intOf, boolOf, evalNumber, type Value } from './gbx/evaluate'
import { type Expr, GbxEvalError, GbxSyntaxError, parse } from './gbx/parse'
import { SeededRng } from './gbx/pcg32'
import {
  available,
  type Book,
  type Choice,
  type Effect,
  type Encounter,
  type Item,
  type Node,
  type StartingItem,
  type StatBonus,
} from './model'
import { Q } from './rational'
import { type EffectiveTier, effectiveTier, progressionEnabled } from './rules'

export type ActionType =
  'choose' | 'take' | 'buy' | 'sell' | 'use' | 'equip' | 'unequip' | 'attack' | 'flee'

export interface Action {
  type: ActionType
  target: string | null
  label: string
  enabled: boolean
  reason: string | null
}

export interface GameEvent {
  type: string
  [k: string]: unknown
}

export class GameError extends Error {}

/** Level-ups handled at once (guards against a formula that makes levels free). */
const MAX_LEVEL_UPS = 100

const MAX_ROUNDS = 200
const GAIN_OPS = new Set(['give', 'equip', 'set_flag', 'learn'])
export const firesOnce = (e: Effect) =>
  (e.once ?? null) !== null ? Boolean(e.once) : GAIN_OPS.has(e.op)

interface Combatant {
  key: string
  name: string
  stats: Record<string, number>
  level: number
}

interface CombatState {
  choice_id: string
  enemies: Combatant[]
  simultaneous: boolean
  flee_allowed: boolean
  round: number
}

export interface GameState {
  tier: string
  stats: Map<string, number>
  max_stats: Map<string, number>
  items: Map<string, number>
  equipped: Map<string, string>
  flags: Set<string>
  skills: Set<string>
  character_class: string | null
  node_id: string | null
  variant_id: string | null
  visits: Map<string, number>
  fired: Set<string>
  shop_stock: Map<string, number>
  combat: CombatState | null
  ended: string | null
  ending_node_id: string | null
  steps: number
}

const sortedObj = <T>(m: Map<string, T>, keep: (v: T) => boolean = () => true) =>
  Object.fromEntries(
    [...m.entries()].filter(([, v]) => keep(v)).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)),
  )
const sortedRec = (r: Record<string, number>) =>
  Object.fromEntries(Object.entries(r).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))

/** The state as JSON, exactly as `GameState.to_dict` writes it. */
export function stateToDict(s: GameState): Record<string, unknown> {
  return {
    tier: s.tier,
    stats: sortedObj(s.stats),
    max_stats: sortedObj(s.max_stats),
    items: sortedObj(s.items, (v) => v > 0),
    equipped: sortedObj(s.equipped),
    flags: [...s.flags].sort(),
    skills: [...s.skills].sort(),
    class: s.character_class,
    node_id: s.node_id,
    variant_id: s.variant_id,
    visits: sortedObj(s.visits),
    combat: s.combat
      ? {
          choice_id: s.combat.choice_id,
          enemies: s.combat.enemies.map((e) => ({
            key: e.key,
            name: e.name,
            level: e.level,
            stats: sortedRec(e.stats),
          })),
          simultaneous: s.combat.simultaneous,
          flee_allowed: s.combat.flee_allowed,
          round: s.combat.round,
        }
      : null,
    ended: s.ended,
    ending_node_id: s.ending_node_id,
    steps: s.steps,
  }
}

// ── env ─────────────────────────────────────────────────────────────────

class GameEnv implements Env {
  readonly tiers: readonly string[]
  readonly currentTier: string
  private playerStat: (key: string) => number
  private refFn: (func: string, key: string) => number | boolean
  private variables: Map<string, Value>
  private objects: Map<string, Record<string, number>>
  constructor(
    tiers: readonly string[],
    currentTier: string,
    playerStat: (key: string) => number,
    refFn: (func: string, key: string) => number | boolean,
    variables: Map<string, Value> = new Map(),
    objects: Map<string, Record<string, number>> = new Map(),
  ) {
    this.tiers = tiers
    this.currentTier = currentTier
    this.playerStat = playerStat
    this.refFn = refFn
    this.variables = variables
    this.objects = objects
  }

  variable(name: string): Value | undefined {
    return this.variables.get(name)
  }
  stat(obj: string, key: string): number {
    if (obj === 'player' && !this.objects.has('player')) return this.playerStat(key)
    const values = this.objects.get(obj)
    // Own keys only: a stat named "constructor" must not find Object.prototype's.
    return values && Object.hasOwn(values, key) ? Math.trunc(values[key]!) : 0
  }
  ref(func: string, key: string): number | boolean {
    return this.refFn(func, key)
  }
  with(
    variables: Record<string, Value> = {},
    objects: Record<string, Record<string, number>> = {},
  ): GameEnv {
    return new GameEnv(
      this.tiers,
      this.currentTier,
      this.playerStat,
      this.refFn,
      new Map([...this.variables, ...Object.entries(variables)]),
      new Map([...this.objects, ...Object.entries(objects)]),
    )
  }
}

const noRefs = (func: string) => (func === 'count' || func === 'visits' ? 0 : false)

/** An enemy's stats at a level (missing or broken formulas are 0). */
export function enemyStats(
  formulas: Record<string, string>,
  level: number,
  stats: Iterable<string>,
  tiers: readonly string[],
  tier: string,
): Record<string, number> {
  const env = new GameEnv(tiers, tier, () => 0, noRefs, new Map([['level', Q.of(level)]]))
  const out: Record<string, number> = {}
  for (const stat of [...stats].sort()) {
    const src = Object.hasOwn(formulas, stat) ? formulas[stat] : undefined
    try {
      out[stat] = src ? intOf(src, env, null) : 0
    } catch (e) {
      if (e instanceof GbxSyntaxError || e instanceof GbxEvalError) out[stat] = 0
      else throw e
    }
  }
  return out
}

// ── combat ──────────────────────────────────────────────────────────────

interface CombatRules {
  playerAttack: Expr
  enemyAttack: Expr
  damage: Expr
  damageStat: string
  hooks: Expr[]
  playerDefeatAt: number
  enemyDefeatAt: number
  statMin: number | null
  fleeAllowed: boolean
}

function combatRules(tier: EffectiveTier): CombatRules | null {
  const c = tier.combat
  if (!(c.player_attack && c.enemy_attack && c.damage_stat)) return null
  const stat = tier.stats.get(c.damage_stat)
  const defeatAt =
    stat && stat.defeat_at !== null && stat.defeat_at !== undefined ? stat.defeat_at : 0
  return {
    playerAttack: parse(c.player_attack),
    enemyAttack: parse(c.enemy_attack),
    damage: parse(c.damage || '2'),
    damageStat: c.damage_stat,
    hooks: c.damage_hooks.map((h) => parse(h)),
    playerDefeatAt: defeatAt,
    enemyDefeatAt: defeatAt,
    statMin: stat ? (stat.min ?? null) : 0,
    fleeAllowed: c.flee_allowed !== false,
  }
}

function rollWith(fn: Expr, env: GameEnv, rng: SeededRng): [number, number] {
  const before = rng.history.length
  const total = evalNumber(fn, env, rng).toInt()
  let natural = 0
  for (const [, , faces] of rng.history.slice(before)) for (const f of faces) natural += f
  return [total, natural]
}

function damageOf(
  rules: CombatRules,
  env: GameEnv,
  rng: SeededRng,
  attacker: Record<string, number>,
  target: Record<string, number>,
  natural: number,
): number {
  const e = env.with({}, { attacker, target })
  let amount = evalNumber(rules.damage, e, rng)
  for (const hook of rules.hooks)
    amount = evalNumber(hook, e.with({ damage: amount, natural: Q.of(natural) }), rng)
  return Math.max(0, amount.toInt())
}

function hit(stats: Record<string, number>, rules: CombatRules, amount: number): number {
  const before = stats[rules.damageStat] ?? 0
  let after = before - amount
  if (rules.statMin !== null) after = Math.max(rules.statMin, after)
  stats[rules.damageStat] = after
  return before - after
}

function fightRound(
  rules: CombatRules,
  env: GameEnv,
  rng: SeededRng,
  player: Record<string, number>,
  enemies: Combatant[],
  simultaneous: boolean,
  roundNo: number,
): GameEvent[] {
  const alive = enemies.filter((e) => (e.stats[rules.damageStat] ?? 0) > rules.enemyDefeatAt)
  if (!alive.length) return []
  const fighting = simultaneous ? alive : alive.slice(0, 1)
  const target = alive[0]!
  const events: GameEvent[] = []
  const pEnv = env.with({}, { player, enemy: target.stats })
  const [pTotal, pNatural] = rollWith(rules.playerAttack, pEnv, rng)
  for (const enemy of fighting) {
    const eEnv = env.with({}, { player, enemy: enemy.stats })
    const [eTotal, eNatural] = rollWith(rules.enemyAttack, eEnv, rng)
    const detail: GameEvent = {
      type: 'combat_round',
      round: roundNo,
      enemy: enemy.key,
      player_attack: pTotal,
      enemy_attack: eTotal,
    }
    if (enemy === target && pTotal > eTotal) {
      const dealt = hit(
        enemy.stats,
        rules,
        damageOf(rules, eEnv, rng, player, enemy.stats, pNatural),
      )
      Object.assign(detail, {
        hit: 'enemy',
        damage: dealt,
        remaining: enemy.stats[rules.damageStat],
      })
    } else if (eTotal > pTotal) {
      const dealt = hit(player, rules, damageOf(rules, eEnv, rng, enemy.stats, player, eNatural))
      Object.assign(detail, { hit: 'player', damage: dealt, remaining: player[rules.damageStat] })
    } else detail.hit = null
    events.push(detail)
    if ((enemy.stats[rules.damageStat] ?? 0) <= rules.enemyDefeatAt && detail.hit === 'enemy')
      events.push({ type: 'enemy_defeated', enemy: enemy.key })
    if ((player[rules.damageStat] ?? 0) <= rules.playerDefeatAt) break
  }
  return events
}

// ── game ────────────────────────────────────────────────────────────────

export interface Creation {
  character_class?: string | null
  fixed_stats?: Record<string, number> | null
}

export class Game {
  readonly book: Book
  readonly tiers: string[]
  readonly tier: EffectiveTier
  readonly seed: number
  rng: SeededRng
  state: GameState
  log: GameEvent[] = []
  private pendingErrors: GameEvent[] = []
  private combatRules: CombatRules | null = null
  readonly currency: string | null
  private nodes: Map<string, Node>
  private itemsById: Map<string, Item>
  private items: Map<string, Item>
  private enemiesById: Map<string, Book['enemies'][number]>
  private enemies: Map<string, Book['enemies'][number]>
  private tables: Map<string, Book['tables'][number]>
  private env: GameEnv
  private quiet = false

  constructor(book: Book, tier: string, seed: number) {
    if (!book.rules) throw new GameError('The series has no active rule system')
    this.book = book
    this.tiers = book.rules.tiers.map((t) => t.key)
    if (!this.tiers.includes(tier)) throw new GameError(`Unknown tier '${tier}'`)
    this.tier = effectiveTier(book.rules.tiers, tier)
    this.seed = seed
    this.rng = new SeededRng(seed)
    this.state = {
      tier,
      stats: new Map(),
      max_stats: new Map(),
      items: new Map(),
      equipped: new Map(),
      flags: new Set(),
      skills: new Set(),
      character_class: null,
      node_id: null,
      variant_id: null,
      visits: new Map(),
      fired: new Set(),
      shop_stock: new Map(),
      combat: null,
      ended: null,
      ending_node_id: null,
      steps: 0,
    }
    try {
      this.combatRules = combatRules(this.tier)
    } catch (e) {
      if (!(e instanceof GbxSyntaxError)) throw e
      this.combatRules = null
      this.pendingErrors.push({ type: 'error', where: 'combat rules', message: e.message })
    }
    this.currency =
      [...this.tier.stats.entries()].find(([, s]) => s.kind === 'resource')?.[0] ?? null
    this.nodes = new Map(book.nodes.map((n) => [n.id, n]))
    const items = book.items.filter((i) => available(book, i))
    this.itemsById = new Map(items.map((i) => [i.id, i]))
    this.items = new Map(items.map((i) => [i.key, i]))
    const enemies = book.enemies.filter((e) => available(book, e))
    this.enemiesById = new Map(enemies.map((e) => [e.id, e]))
    this.enemies = new Map(enemies.map((e) => [e.key, e]))
    this.tables = new Map(book.tables.filter((t) => available(book, t)).map((t) => [t.id, t]))
    this.env = new GameEnv(
      this.tiers,
      tier,
      (k) => this.stat(k),
      (f, k) => this.ref(f, k),
    )
  }

  // ── queries ──

  get node(): Node | null {
    return this.nodes.get(this.state.node_id ?? '') ?? null
  }

  tierAllows(minTier: string | null | undefined): boolean {
    if (minTier === null || minTier === undefined || !this.tiers.includes(minTier))
      return minTier === null || minTier === undefined
    return this.tiers.indexOf(minTier) <= this.tiers.indexOf(this.state.tier)
  }

  /** Effective player stat: base value plus item modifiers. */
  stat(key: string): number {
    let value = this.state.stats.get(key) ?? 0
    for (const [itemKey, count] of this.state.items) {
      if (count <= 0) continue
      const item = this.items.get(itemKey)
      if (!item || !item.modifiers?.length) continue
      if (item.slot && this.state.equipped.get(item.slot) !== itemKey) continue
      for (const m of item.modifiers)
        if (m.stat === key && this.tierAllows(m.min_tier))
          value += this.int(m.amount, `item ${itemKey} modifier`, { rng: false })
    }
    return value
  }

  /** Effective stats for display: broken modifiers count as 0 without logging errors. */
  peekStats(): Record<string, number> {
    this.quiet = true
    try {
      return this.effectiveStats()
    } finally {
      this.quiet = false
    }
  }

  effectiveStats(): Record<string, number> {
    const out: Record<string, number> = {}
    for (const [k, s] of this.tier.stats) if (s.applies_to.includes('player')) out[k] = this.stat(k)
    return out
  }

  private ref(func: string, key: string): number | boolean {
    const s = this.state
    switch (func) {
      case 'has':
        return (s.items.get(key) ?? 0) > 0
      case 'count':
        return s.items.get(key) ?? 0
      case 'equipped':
        return [...s.equipped.values()].includes(key)
      case 'flag':
        return s.flags.has(key)
      case 'skill':
        return s.skills.has(key)
      case 'class':
        return s.character_class === key
      case 'visits':
        return s.visits.get(key) ?? 0
    }
    return false
  }

  // ── expression helpers (content errors become events, never crashes) ──

  private error(where: string, e: unknown): void {
    if (this.quiet) return
    this.log.push({ type: 'error', where, message: e instanceof Error ? e.message : String(e) })
  }

  private int(src: string, where: string, opts: { rng?: boolean; env?: GameEnv } = {}): number {
    try {
      return intOf(src, opts.env ?? this.env, opts.rng === false ? null : this.rng)
    } catch (e) {
      if (e instanceof GbxSyntaxError || e instanceof GbxEvalError) {
        this.error(where, e)
        return 0
      }
      throw e
    }
  }

  /** Whether a condition holds now, with no side effects (errors count as false). */
  holds(src: string | null | undefined): boolean {
    if (!src) return true
    try {
      return boolOf(src, this.env)
    } catch {
      return false
    }
  }

  private bool(src: string | null | undefined, where: string, env?: GameEnv): boolean {
    if (!src) return true
    try {
      return boolOf(src, env ?? this.env)
    } catch (e) {
      if (e instanceof GbxSyntaxError || e instanceof GbxEvalError) {
        this.error(where, e)
        return false
      }
      throw e
    }
  }

  private roll(src: string, purpose: string): number {
    const before = this.rng.history.length
    const total = this.int(src, purpose)
    const faces = this.rng.history.slice(before).flatMap(([, , fs]) => fs)
    this.log.push({ type: 'roll', purpose, expr: src, faces, total })
    return total
  }

  // ── setup ──

  start(creation: Creation = {}): GameEvent[] {
    const mark = this.log.length
    if (this.state.node_id !== null) throw new GameError('The game has already started')
    this.log.push(...this.pendingErrors)
    for (const [key, sd] of this.tier.stats) {
      if (!sd.applies_to.includes('player')) continue
      const fixed = creation.fixed_stats
      const value = fixed && key in fixed ? fixed[key]! : this.roll(sd.initial, `initial ${key}`)
      this.state.stats.set(key, value)
      if (sd.max_is_initial) this.state.max_stats.set(key, value)
      else if (sd.max !== null && sd.max !== undefined) this.state.max_stats.set(key, sd.max)
    }
    if (this.tier.classes.size) {
      const chosen = creation.character_class || [...this.tier.classes.keys()][0]!
      const cls = this.tier.classes.get(chosen)
      if (!cls) throw new GameError(`Unknown class '${chosen}'`)
      this.state.character_class = cls.key
      for (const s of cls.skills) this.state.skills.add(s)
      for (const b of cls.modifiers ?? []) this.bonus(b, `class ${cls.key} bonus`)
    }
    this.log.push({
      type: 'character_created',
      stats: sortedObj(this.state.stats),
      class: this.state.character_class,
    })
    const cls = this.tier.classes.get(this.state.character_class ?? '')
    this.startingItems([...this.tier.startingItems, ...(cls?.starting_items ?? [])])
    const start = this.nodes.get(this.book.start_node_id ?? '')
    if (!start) this.end('stuck', null, 'The book has no start node')
    else this.enter(start)
    return this.log.slice(mark)
  }

  private startingItems(entries: StartingItem[]): void {
    for (const si of entries) {
      const item = this.items.get(si.item)
      if (!item) {
        this.error('starting items', new GbxEvalError(`unknown item ${si.item}`))
        continue
      }
      const got = this.give(item.key, si.qty)
      this.log.push({ type: 'effect', source: 'start', op: 'give', item: item.key, qty: got })
      if (
        si.equip &&
        item.slot !== null &&
        this.tier.slots.includes(item.slot) &&
        (this.state.items.get(item.key) ?? 0) > 0
      ) {
        this.state.equipped.set(item.slot, item.key)
        this.log.push({ type: 'effect', source: 'start', op: 'equip', item: item.key })
      }
    }
  }

  // ── progression ──

  /** The reader's level (1 when the rules have no levels). */
  level(): number {
    const key = this.tier.progression.level_stat
    return key && this.tier.stats.has(key) ? (this.state.stats.get(key) ?? 1) : 1
  }

  /** XP the next level costs, for display (null without levels or at the top). */
  xpNeeded(): number | null {
    const pr = this.tier.progression
    if (!progressionEnabled(pr) || !this.tier.stats.has(pr.level_stat!)) return null
    const level = this.state.stats.get(pr.level_stat!) ?? 0
    const cap = this.state.max_stats.get(pr.level_stat!)
    if ((pr.max_level !== null && level >= pr.max_level) || (cap !== undefined && level >= cap))
      return null
    const quiet = this.quiet
    this.quiet = true
    try {
      const env = this.env.with({ level: Q.of(level) })
      const need = this.int(pr.xp_to_next!, 'XP for the next level', { rng: false, env })
      return need > 0 ? need : null
    } finally {
      this.quiet = quiet
    }
  }

  /** Raise a player stat (and a starting-value maximum) by a bonus; returns the change. */
  private bonus(b: StatBonus, where: string): number {
    const sd = this.tier.stats.get(b.stat)
    if (!sd || !sd.applies_to.includes('player')) return 0
    const amount = this.int(b.amount, where, { env: this.env.with({ level: Q.of(this.level()) }) })
    const cap = this.state.max_stats.get(b.stat)
    if (sd.max_is_initial && cap !== undefined) this.state.max_stats.set(b.stat, cap + amount)
    const before = this.state.stats.get(b.stat) ?? 0
    return this.setStat(b.stat, before + amount) - before
  }

  private awardXp(enemies: Combatant[]): void {
    const pr = this.tier.progression
    if (!progressionEnabled(pr) || !pr.xp_award || !this.tier.stats.has(pr.xp_stat!)) return
    let total = 0
    for (const e of enemies) {
      const env = this.env.with({ enemy_level: Q.of(e.level), level: Q.of(this.level()) })
      total += this.int(pr.xp_award, 'XP award', { env })
    }
    const xp = pr.xp_stat!
    const before = this.state.stats.get(xp) ?? 0
    const after = this.setStat(xp, before + total)
    this.log.push({ type: 'xp_gained', stat: xp, amount: after - before, value: after })
    this.checkLevelUp()
  }

  private checkLevelUp(): void {
    const pr = this.tier.progression
    const xpKey = pr.xp_stat
    const levelKey = pr.level_stat
    if (
      !progressionEnabled(pr) ||
      !this.tier.stats.has(xpKey!) ||
      !this.tier.stats.has(levelKey!) ||
      xpKey === levelKey
    )
      return
    for (let n = 0; n < MAX_LEVEL_UPS; n++) {
      const level = this.state.stats.get(levelKey!) ?? 0
      const cap = this.state.max_stats.get(levelKey!)
      if ((pr.max_level !== null && level >= pr.max_level) || (cap !== undefined && level >= cap))
        return
      const env = this.env.with({ level: Q.of(level) })
      const need = this.int(pr.xp_to_next!, 'XP for the next level', { rng: false, env })
      const xp = this.state.stats.get(xpKey!) ?? 0
      if (need <= 0 || xp < need) return
      this.setStat(xpKey!, xp - need)
      const now = this.setStat(levelKey!, level + 1)
      this.log.push({
        type: 'level_up',
        stat: levelKey,
        level: now,
        xp: this.state.stats.get(xpKey!) ?? 0,
      })
      for (const b of pr.level_up ?? []) {
        const change = this.bonus(b, 'level-up bonus')
        this.log.push({
          type: 'effect',
          source: 'level_up',
          op: 'modify',
          stat: b.stat,
          change,
          value: this.state.stats.get(b.stat) ?? 0,
        })
      }
    }
  }

  // ── effects ──

  private setStat(key: string, value: number): number {
    const sd = this.tier.stats.get(key)
    if (sd) {
      if (sd.min !== null && sd.min !== undefined) value = Math.max(sd.min, value)
      const cap = this.state.max_stats.get(key)
      if (cap !== undefined) value = Math.min(cap, value)
    }
    this.state.stats.set(key, value)
    return value
  }

  private give(key: string, qty: number): number {
    const item = this.items.get(key)
    const have = this.state.items.get(key) ?? 0
    let n = have + qty
    if (item && item.max_stack !== null && item.max_stack !== undefined)
      n = Math.min(n, item.max_stack)
    this.state.items.set(key, n)
    return n - have
  }

  private take(key: string, qty: number): number {
    const have = this.state.items.get(key) ?? 0
    const n = Math.max(0, have - qty)
    this.state.items.set(key, n)
    if (n === 0)
      for (const [slot, k] of [...this.state.equipped])
        if (k === key) this.state.equipped.delete(slot)
    return have - n
  }

  private apply(
    effects: Effect[],
    source: string,
    opts: { respectOnce?: boolean; checkDefeat?: boolean } = {},
  ): void {
    const respectOnce = opts.respectOnce ?? true
    const xpKey = this.tier.progression.xp_stat
    let xpTouched = false
    effects.forEach((eff, i) => {
      if (!this.tierAllows(eff.min_tier)) return
      const onceKey = `${source}:${i}`
      if (respectOnce && firesOnce(eff)) {
        if (this.state.fired.has(onceKey)) return
        this.state.fired.add(onceKey)
      }
      const where = `${source} effect ${i + 1}`
      const data: GameEvent = { type: 'effect', source, op: eff.op }
      switch (eff.op) {
        case 'modify': {
          const delta = this.int(eff.amount!, where)
          const before = this.state.stats.get(eff.stat!) ?? 0
          const after = this.setStat(eff.stat!, before + delta)
          Object.assign(data, { stat: eff.stat, change: after - before, value: after })
          break
        }
        case 'set': {
          const after = this.setStat(eff.stat!, this.int(eff.value!, where))
          Object.assign(data, { stat: eff.stat, value: after })
          break
        }
        case 'give':
          Object.assign(data, { item: eff.item, qty: this.give(eff.item!, eff.qty ?? 1) })
          break
        case 'take':
          Object.assign(data, { item: eff.item, qty: this.take(eff.item!, eff.qty ?? 1) })
          break
        case 'equip': {
          const item = this.items.get(eff.item!)
          if (
            item &&
            item.slot !== null &&
            this.tier.slots.includes(item.slot) &&
            (this.state.items.get(eff.item!) ?? 0) > 0
          )
            this.state.equipped.set(item.slot, eff.item!)
          data.item = eff.item
          break
        }
        case 'set_flag':
          this.state.flags.add(eff.flag!)
          data.flag = eff.flag
          break
        case 'clear_flag':
          this.state.flags.delete(eff.flag!)
          data.flag = eff.flag
          break
        case 'learn':
          this.state.skills.add(eff.skill!)
          data.skill = eff.skill
          break
      }
      this.log.push(data)
      xpTouched ||= xpKey !== null && data.stat === xpKey
    })
    if (xpTouched) this.checkLevelUp()
    if (opts.checkDefeat ?? true) this.checkDefeat()
  }

  private checkDefeat(inCombat = false): void {
    if (this.state.ended || (this.state.combat !== null && !inCombat)) return
    for (const [key, sd] of this.tier.stats) {
      if (
        sd.defeat_at !== null &&
        sd.defeat_at !== undefined &&
        sd.applies_to.includes('player') &&
        (this.state.stats.get(key) ?? 0) <= sd.defeat_at
      ) {
        this.state.combat = null
        this.end('defeated', null, `${sd.label} reached ${sd.defeat_at}`)
        return
      }
    }
  }

  private end(kind: string, node: Node | null, reason?: string): void {
    this.state.ended = kind
    this.state.ending_node_id = node ? node.id : null
    const data: GameEvent = { type: 'game_over', ending: kind, node: node ? node.id : null }
    if (reason) data.reason = reason
    this.log.push(data)
  }

  // ── movement ──

  private enter(node: Node): void {
    const s = this.state
    s.node_id = node.id
    s.visits.set(node.key, (s.visits.get(node.key) ?? 0) + 1)
    let variant = null
    for (const v of [...node.variants].sort((a, b) => b.priority - a.priority)) {
      if (this.bool(v.condition, `variant ${v.label}`)) {
        variant = v
        break
      }
    }
    s.variant_id = variant ? variant.id : null
    this.log.push({
      type: 'enter',
      node: node.id,
      key: node.key,
      variant: s.variant_id,
      visit: s.visits.get(node.key),
    })
    // An authored ending takes precedence over stat defeat.
    this.apply(node.on_enter, `enter:${node.id}`, { checkDefeat: node.ending_kind == null })
    if (s.ended) return
    if (node.ending_kind != null) {
      this.end(node.ending_kind, node)
      return
    }
    this.choices(true) // report broken choice conditions once, on arrival
    this.checkStuck()
  }

  private checkStuck(): void {
    if (!this.state.ended && !this.available().length)
      this.end('stuck', this.node, 'Nothing can be done here')
  }

  private go(choice: Choice, outcomeKey: string): void {
    const outcome = choice.outcomes.find((o) => o.key === outcomeKey)
    this.log.push({ type: 'outcome', choice: choice.id, outcome: outcomeKey })
    const target = outcome ? this.nodes.get(outcome.target_id ?? '') : undefined
    if (!target) {
      this.end(
        'stuck',
        this.node,
        `Choice '${choice.label}' has no destination for '${outcomeKey}'`,
      )
      return
    }
    this.enter(target)
  }

  // ── actions ──

  private choices(log = false): [Choice, boolean][] {
    const node = this.node
    if (!node) return []
    this.quiet = !log
    try {
      const out: [Choice, boolean][] = []
      for (const c of node.choices) {
        if (!this.tierAllows(c.min_tier)) continue
        const ok = this.bool(c.condition, `choice ${c.label} condition`)
        if (ok || c.unmet_display === 'show_disabled') out.push([c, ok])
      }
      return out
    } finally {
      this.quiet = false
    }
  }

  /** Everything the reader could do now, including disabled options. */
  actions(): Action[] {
    const s = this.state
    if (s.ended || !this.node) return []
    const act = (
      type: ActionType,
      target: string | null,
      label: string,
      enabled = true,
      reason: string | null = null,
    ): Action => ({
      type,
      target,
      label,
      enabled,
      reason,
    })
    const out: Action[] = []
    if (s.combat) {
      out.push(act('attack', null, 'Attack'))
      if (s.combat.flee_allowed) out.push(act('flee', null, 'Flee'))
      return [...out, ...this.itemActions(true)]
    }
    const node = this.node
    for (const [c, ok] of this.choices())
      out.push(act('choose', c.id, c.label, ok, ok ? null : 'Condition not met'))
    node.items.forEach((p, i) => {
      const item = this.itemsById.get(p.item_id)
      if (item && !s.fired.has(`take:${node.id}:${i}`))
        out.push(act('take', String(i), `Take ${item.name}` + (p.qty > 1 ? ` x${p.qty}` : '')))
    })
    if (node.shop !== null && node.shop !== undefined) {
      const gold = this.currency ? (s.stats.get(this.currency) ?? 0) : 0
      node.shop.forEach((entry, i) => {
        const item = this.itemsById.get(entry.item_id)
        if (!item) return
        const stock =
          s.shop_stock.get(`${node.id}:${i}`) ??
          (entry.stock !== null && entry.stock !== undefined ? entry.stock : -1)
        let reason: string | null = null
        if (stock === 0) reason = 'Sold out'
        else if (this.currency === null || gold < entry.price) reason = 'Not enough money'
        else if (
          item.max_stack !== null &&
          item.max_stack !== undefined &&
          (s.items.get(item.key) ?? 0) >= item.max_stack
        )
          reason = "Can't carry more"
        out.push(
          act('buy', String(i), `Buy ${item.name} (${entry.price})`, reason === null, reason),
        )
      })
      if (node.shop_sell_rate && this.currency !== null) {
        for (const [key, count] of [...s.items].sort(([a], [b]) => (a < b ? -1 : 1))) {
          const item = this.items.get(key)
          if (count > 0 && item && item.value > 0 && item.category !== 'key') {
            const price = Math.floor((item.value * node.shop_sell_rate) / 100)
            out.push(act('sell', key, `Sell ${item.name} (${price})`))
          }
        }
      }
    }
    return [...out, ...this.itemActions(false)]
  }

  private itemActions(inCombat: boolean): Action[] {
    const s = this.state
    const out: Action[] = []
    for (const [key, count] of [...s.items].sort(([a], [b]) => (a < b ? -1 : 1))) {
      const item = this.items.get(key)
      if (count <= 0 || !item) continue
      if (item.category === 'consumable' && item.use_effects?.length)
        out.push({
          type: 'use',
          target: key,
          label: `Use ${item.name}`,
          enabled: true,
          reason: null,
        })
      if (
        !inCombat &&
        item.slot &&
        this.tier.slots.includes(item.slot) &&
        s.equipped.get(item.slot) !== key
      )
        out.push({
          type: 'equip',
          target: key,
          label: `Equip ${item.name}`,
          enabled: true,
          reason: null,
        })
    }
    if (!inCombat)
      for (const [slot, key] of [...s.equipped].sort(([a], [b]) => (a < b ? -1 : 1))) {
        const item = this.items.get(key)
        out.push({
          type: 'unequip',
          target: slot,
          label: `Unequip ${item ? item.name : key}`,
          enabled: true,
          reason: null,
        })
      }
    return out
  }

  available(): Action[] {
    return this.actions().filter((a) => a.enabled)
  }

  /** Perform an action; returns the events it produced. */
  step(action: { type: ActionType; target?: string | null }): GameEvent[] {
    if (this.state.ended) throw new GameError('The game is over')
    const target = action.target ?? null
    if (!this.available().some((a) => a.type === action.type && a.target === target))
      throw new GameError(`Action ${action.type} ${target ?? ''} is not available`)
    const mark = this.log.length
    this.rng.history.length = 0 // only this step's dice matter
    this.state.steps += 1
    this.log.push({ type: 'action', action: action.type, target })
    switch (action.type) {
      case 'choose':
        this.choose(target ?? '')
        break
      case 'attack':
        this.attack()
        break
      case 'flee':
        this.flee()
        break
      case 'take':
        this.takeFound(Number(target ?? 0))
        break
      case 'buy':
        this.buy(Number(target ?? 0))
        break
      case 'sell':
        this.sell(target ?? '')
        break
      case 'use':
        this.use(target ?? '')
        break
      case 'equip': {
        const item = this.items.get(target ?? '')!
        this.state.equipped.set(item.slot!, item.key)
        this.log.push({ type: 'equipped', item: item.key, slot: item.slot })
        break
      }
      case 'unequip': {
        const key = this.state.equipped.get(target ?? '')!
        this.state.equipped.delete(target ?? '')
        this.log.push({ type: 'unequipped', item: key, slot: target })
        break
      }
    }
    this.checkStuck()
    return this.log.slice(mark)
  }

  private choose(choiceId: string): void {
    const node = this.node!
    const choice = node.choices.find((c) => c.id === choiceId)!
    this.apply(choice.effects, `choice:${choice.id}`)
    if (this.state.ended) return
    switch (choice.kind) {
      case 'goto':
        this.go(choice, 'default')
        break
      case 'roll': {
        const total = this.roll(choice.dice || '2d6', `choice ${choice.label}`)
        const hit = choice.outcomes.find(
          (o) =>
            o.range_lo !== null &&
            o.range_lo !== undefined &&
            o.range_hi !== null &&
            o.range_hi !== undefined &&
            o.range_lo <= total &&
            total <= o.range_hi,
        )
        if (!hit) this.end('stuck', node, `No outcome covers a roll of ${total}`)
        else this.go(choice, hit.key)
        break
      }
      case 'test':
        this.test(choice)
        break
      case 'combat':
        this.startCombat(choice)
        break
    }
  }

  private test(choice: Choice): void {
    const test = this.tier.tests.get(choice.test ?? '')
    if (!test) {
      this.end('stuck', this.node, `Unknown test '${choice.test}'`)
      return
    }
    const total = this.roll(test.roll, `test ${test.key}`)
    const env = this.env.with({ roll: Q.of(total) })
    const success = this.bool(test.success, `test ${test.key}`, env)
    this.log.push({ type: 'test', test: test.key, roll: total, success })
    this.apply(test.after, `test:${test.key}`, { respectOnce: false })
    if (!this.state.ended) this.go(choice, success ? 'success' : 'failure')
  }

  // ── combat ──

  private enemyStatKeys(): string[] {
    return [...this.tier.stats].filter(([, s]) => s.applies_to.includes('enemy')).map(([k]) => k)
  }

  private encounterEnemies(enc: Encounter): Combatant[] | null {
    const keys = this.enemyStatKeys()
    let enemies: [string, number, number][] = []
    if (enc.mode === 'fixed') {
      for (const ee of enc.enemies) {
        const enemy = this.enemiesById.get(ee.enemy_id)
        if (enemy) enemies.push([enemy.key, ee.level, ee.count])
      }
    } else {
      const table = this.tables.get(enc.table_id ?? '')
      if (!table) return []
      const total = this.roll(table.dice, `table ${table.key}`)
      const entry = table.entries.find((e) => e.lo <= total && total <= e.hi)
      this.log.push({
        type: 'table',
        table: table.key,
        roll: total,
        result: entry ? entry.kind : null,
      })
      if (!entry || entry.kind === 'nothing') return null
      if (entry.kind === 'item' && entry.item) {
        this.give(entry.item, entry.qty)
        this.log.push({
          type: 'effect',
          source: `table:${table.key}`,
          op: 'give',
          item: entry.item,
          qty: entry.qty,
        })
        return null
      }
      if (entry.kind === 'gold') {
        if (this.currency) {
          const amount = this.int(entry.amount || '0', `table ${table.key}`)
          this.setStat(this.currency, (this.state.stats.get(this.currency) ?? 0) + amount)
        }
        return null
      }
      enemies = entry.enemies.map((e) => [...e] as [string, number, number])
    }
    const out: Combatant[] = []
    for (const [key, level, count] of enemies) {
      const enemy = this.enemies.get(key)
      if (!enemy) continue
      for (let n = 0; n < count; n++)
        out.push({
          key: count > 1 ? `${key}#${n + 1}` : key,
          name: enemy.name,
          stats: enemyStats(enemy.stat_formulas, level, keys, this.tiers, this.state.tier),
          level,
        })
    }
    return out
  }

  private startCombat(choice: Choice): void {
    const node = this.node!
    const enc = node.encounters.find((e) => e.id === choice.encounter_id)
    if (!enc) {
      this.end('stuck', node, `Choice '${choice.label}' has no encounter`)
      return
    }
    const enemies = this.encounterEnemies(enc)
    if (!enemies || !enemies.length) {
      this.log.push({ type: 'combat_skipped', encounter: enc.id })
      this.go(choice, 'win')
      return
    }
    if (!this.combatRules) {
      this.log.push({ type: 'combat_unconfigured', encounter: enc.id })
      this.go(choice, 'win')
      return
    }
    this.state.combat = {
      choice_id: choice.id,
      enemies,
      simultaneous: enc.fight === 'simultaneous',
      flee_allowed: choice.flee_allowed && this.combatRules.fleeAllowed,
      round: 0,
    }
    this.log.push({
      type: 'combat_start',
      encounter: enc.id,
      enemies: enemies.map((e) => ({
        key: e.key,
        name: e.name,
        level: e.level,
        stats: sortedRec(e.stats),
      })),
    })
  }

  private finishCombat(outcome: string): void {
    const cs = this.state.combat!
    this.state.combat = null
    this.log.push({ type: 'combat_end', outcome, rounds: cs.round })
    if (outcome === 'win') this.awardXp(cs.enemies)
    const choice = this.node!.choices.find((c) => c.id === cs.choice_id)!
    this.go(choice, outcome)
  }

  private attack(): void {
    const cs = this.state.combat!
    const rules = this.combatRules!
    cs.round += 1
    const player = this.effectiveStats()
    const before = player[rules.damageStat] ?? 0
    try {
      this.log.push(
        ...fightRound(rules, this.env, this.rng, player, cs.enemies, cs.simultaneous, cs.round),
      )
    } catch (e) {
      if (!(e instanceof GbxEvalError)) throw e
      this.error('combat', e)
      this.state.combat = null
      this.end('stuck', this.node, `Combat rules failed: ${e.message}`)
      return
    }
    const delta = (player[rules.damageStat] ?? 0) - before
    if (delta) this.setStat(rules.damageStat, (this.state.stats.get(rules.damageStat) ?? 0) + delta)
    if ((this.state.stats.get(rules.damageStat) ?? 0) <= rules.playerDefeatAt)
      this.finishCombat('lose')
    else if (cs.enemies.every((e) => (e.stats[rules.damageStat] ?? 0) <= rules.enemyDefeatAt))
      this.finishCombat('win')
    else if (cs.round >= MAX_ROUNDS) {
      this.log.push({ type: 'combat_stalemate', rounds: cs.round })
      this.finishCombat('lose')
    }
  }

  private flee(): void {
    this.apply(this.tier.combat.flee_cost ?? [], 'flee', { respectOnce: false })
    this.finishCombat('flee')
    this.checkDefeat()
  }

  // ── items ──

  private takeFound(index: number): void {
    const node = this.node!
    const p = node.items[index]!
    const item = this.itemsById.get(p.item_id)!
    this.state.fired.add(`take:${node.id}:${index}`)
    const got = this.give(item.key, p.qty)
    this.log.push({ type: 'item_taken', item: item.key, qty: got })
  }

  private buy(index: number): void {
    const node = this.node!
    const entry = node.shop![index]!
    const item = this.itemsById.get(entry.item_id)!
    const key = `${node.id}:${index}`
    if (entry.stock !== null && entry.stock !== undefined)
      this.state.shop_stock.set(key, (this.state.shop_stock.get(key) ?? entry.stock) - 1)
    this.setStat(this.currency!, (this.state.stats.get(this.currency!) ?? 0) - entry.price)
    this.give(item.key, 1)
    this.log.push({ type: 'item_bought', item: item.key, price: entry.price })
  }

  private sell(key: string): void {
    const node = this.node!
    const item = this.items.get(key)!
    const price = Math.floor((item.value * node.shop_sell_rate!) / 100)
    this.take(key, 1)
    this.setStat(this.currency!, (this.state.stats.get(this.currency!) ?? 0) + price)
    this.log.push({ type: 'item_sold', item: key, price })
  }

  private use(key: string): void {
    const item = this.items.get(key)!
    this.take(key, 1)
    this.log.push({ type: 'item_used', item: key })
    this.apply(item.use_effects, `use:${key}`, { respectOnce: false })
    this.checkDefeat(true)
  }
}
