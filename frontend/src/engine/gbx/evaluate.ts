/**
 * gbx evaluation, matching the Python engine's compiled path (`core/gbx/compiler.py`)
 * value for value: exact rationals, Python equality (`1 == true`), floor rounding,
 * short-circuit `and`/`or`, and the same error messages.
 */
import { Q } from '../rational'
import { type Expr, GbxEvalError, parse } from './parse'
import type { Rng } from './pcg32'

export interface Tier {
  tier: number
}
export type Value = Q | boolean | Tier

export interface Env {
  tiers: readonly string[]
  currentTier: string
  variable(name: string): Value | undefined
  stat(obj: string, key: string): number
  ref(func: string, key: string): number | boolean
}

const REF_FUNCTIONS = new Set(['has', 'count', 'equipped', 'flag', 'skill', 'class', 'visits'])
const MATH: Record<string, [number, number | null]> = {
  min: [2, null],
  max: [2, null],
  floor: [1, 1],
  ceil: [1, 1],
  round: [1, 1],
  abs: [1, 1],
  clamp: [3, 3],
}
const HALF = Q.of(1, 2)

const isQ = (v: Value): v is Q => v instanceof Q
const isTier = (v: Value): v is Tier => typeof v === 'object' && !(v instanceof Q)

/** Python repr of a value as the compiled path holds it (ints stay ints). */
export function repr(v: Value): string {
  if (typeof v === 'boolean') return v ? 'True' : 'False'
  if (isQ(v)) return v.d === 1n ? v.n.toString() : `Fraction(${v.n}, ${v.d})`
  return `TierValue(index=${v.tier})`
}

class Evaluator {
  private env: Env
  private rng: Rng | null
  private bare: string | null
  constructor(env: Env, rng: Rng | null, bare: string | null) {
    this.env = env
    this.rng = rng
    this.bare = bare
  }

  num(e: Expr): Q {
    const v = this.eval(e)
    if (!isQ(v)) throw new GbxEvalError(`expected a number, got ${repr(v)}`)
    return v
  }

  bool(e: Expr): boolean {
    const v = this.eval(e)
    if (typeof v !== 'boolean') throw new GbxEvalError(`expected true/false, got ${repr(v)}`)
    return v
  }

  eval(e: Expr): Value {
    switch (e.t) {
      case 'num':
        return Q.of(e.v)
      case 'bool':
        return e.v
      case 'dice': {
        if (!this.rng) throw new GbxEvalError('dice rolled without a random source')
        return Q.of(this.rng.roll(e.n, e.s).reduce((a, b) => a + b, 0))
      }
      case 'name': {
        const v = this.env.variable(e.n)
        if (v !== undefined) return v
        const { tiers, currentTier } = this.env
        if (e.n === 'tier') {
          if (!tiers.includes(currentTier))
            throw new GbxEvalError(`current tier '${currentTier}' is unknown`)
          return { tier: tiers.indexOf(currentTier) }
        }
        if (tiers.includes(e.n)) return { tier: tiers.indexOf(e.n) }
        if (this.bare !== null) return Q.of(this.env.stat(this.bare, e.n))
        throw new GbxEvalError(`unknown name ${e.n}`)
      }
      case 'attr':
        return Q.of(this.env.stat(e.o, e.a))
      case 'call':
        return this.call(e.f, e.a)
      case 'unary':
        return e.op === 'not' ? !this.bool(e.x) : this.num(e.x).neg()
      case 'bin': {
        if (e.op === 'and') return this.bool(e.l) && this.bool(e.r)
        if (e.op === 'or') return this.bool(e.l) || this.bool(e.r)
        const a = this.num(e.l)
        const b = this.num(e.r)
        switch (e.op) {
          case '+':
            return a.add(b)
          case '-':
            return a.sub(b)
          case '*':
            return a.mul(b)
        }
        if (b.isZero()) throw new GbxEvalError('division by zero')
        return e.op === '/' ? a.div(b) : a.mod(b)
      }
      case 'cmp':
        return compare(e.op, this.eval(e.l), this.eval(e.r))
      case 'if':
        return this.bool(e.c) ? this.eval(e.y) : this.eval(e.n)
    }
  }

  call(f: string, args: Expr[]): Value {
    if (REF_FUNCTIONS.has(f)) {
      const arg = args.length === 1 ? args[0]! : null
      if (!arg || arg.t !== 'name') throw new GbxEvalError(`${f}() needs a key`)
      const r = this.env.ref(f, arg.n)
      return typeof r === 'boolean' ? r : Q.of(Math.trunc(r))
    }
    const arity = MATH[f]
    if (arity && (args.length < arity[0] || (arity[1] !== null && args.length > arity[1])))
      throw new GbxEvalError(`${f}() got ${args.length} argument(s)`)
    if (!arity) throw new GbxEvalError(`unknown function ${f}`)
    const vals = args.map((a) => this.num(a)) // source order: dice draws match
    switch (f) {
      case 'min':
        return vals.reduce((best, v) => (v.cmp(best) < 0 ? v : best))
      case 'max':
        return vals.reduce((best, v) => (v.cmp(best) > 0 ? v : best))
      case 'floor':
        return vals[0]!.floorQ()
      case 'ceil':
        return Q.of(vals[0]!.ceil())
      case 'round':
        return vals[0]!.add(HALF).floorQ()
      case 'abs':
        return vals[0]!.abs()
      default: {
        // clamp(value, lo, hi) = max(lo, min(hi, value))
        const [v, lo, hi] = vals as [Q, Q, Q]
        const inner = v.cmp(hi) < 0 ? v : hi
        return inner.cmp(lo) > 0 ? inner : lo
      }
    }
  }
}

function pyEquals(a: Value, b: Value): boolean {
  if (isTier(a) || isTier(b)) return isTier(a) && isTier(b) && a.tier === b.tier
  const toQ = (v: Q | boolean) => (typeof v === 'boolean' ? Q.of(v ? 1 : 0) : v)
  if (typeof a === 'boolean' && typeof b === 'boolean') return a === b
  return toQ(a).eq(toQ(b)) // Python: True == 1
}

function compare(op: string, a: Value, b: Value): boolean {
  if (op === '==') return pyEquals(a, b)
  if (op === '!=') return !pyEquals(a, b)
  let c: number
  if (isQ(a) && isQ(b)) c = a.cmp(b)
  else if (isTier(a) && isTier(b)) c = a.tier - b.tier
  else throw new GbxEvalError(`can't order ${repr(a)} and ${repr(b)}`)
  if (op === '<') return c < 0
  if (op === '<=') return c <= 0
  if (op === '>') return c > 0
  return c >= 0
}

export function evaluate(
  e: Expr,
  env: Env,
  rng: Rng | null,
  bare: string | null = 'player',
): Value {
  return new Evaluator(env, rng, bare).eval(e)
}

export function evalNumber(e: Expr, env: Env, rng: Rng | null, bare: string | null = 'player'): Q {
  return new Evaluator(env, rng, bare).num(e)
}

/** Results beyond this are errors in both engines (doubles are exact to 2**53). */
const MAX_INT = 2n ** 53n

/** A number rounded down (as `compiled_int`). Throws GbxSyntaxError / GbxEvalError. */
export function intOf(src: string, env: Env, rng: Rng | null): number {
  const value = evalNumber(parse(src), env, rng).floor()
  if (value > MAX_INT || value < -MAX_INT) throw new GbxEvalError('number too large')
  return Number(value)
}

/** A condition (as `compiled_bool`). Throws GbxSyntaxError / GbxEvalError. */
export function boolOf(src: string, env: Env, rng: Rng | null = null): boolean {
  return new Evaluator(env, rng, 'player').bool(parse(src))
}
