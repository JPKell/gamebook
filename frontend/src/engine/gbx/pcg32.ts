/**
 * Portable dice: PCG32 (XSH-RR), identical to the Python engine's `SeededRng`
 * (ADR 0006). Bounded rolls use rejection sampling. Every roll is recorded.
 */
const MASK64 = (1n << 64n) - 1n
const MULT = 6364136223846793005n
const INC = 1442695040888963407n

export interface Rng {
  roll(count: number, sides: number): number[]
}

export class SeededRng implements Rng {
  readonly seed: number
  history: [number, number, number[]][] = []
  private state = 0n

  constructor(seed: number) {
    this.seed = seed
    this.state = 0n
    this.next32()
    this.state = (this.state + (BigInt(seed) & MASK64)) & MASK64
    this.next32()
  }

  private next32(): number {
    const old = this.state
    this.state = (old * MULT + INC) & MASK64
    const xorshifted = (((old >> 18n) ^ old) >> 27n) & 0xffffffffn
    const rot = old >> 59n
    const out = ((xorshifted >> rot) | (xorshifted << (-rot & 31n))) & 0xffffffffn
    return Number(out)
  }

  /** Uniform integer in [0, bound). */
  below(bound: number): number {
    const threshold = (0x100000000 - bound) % bound
    for (;;) {
      const r = this.next32()
      if (r >= threshold) return r % bound
    }
  }

  roll(count: number, sides: number): number[] {
    const faces = Array.from({ length: count }, () => this.below(sides) + 1)
    this.history.push([count, sides, faces])
    return faces
  }

  clone(): SeededRng {
    const c = Object.create(SeededRng.prototype) as SeededRng
    Object.assign(c, this, { history: this.history.map(([n, s, f]) => [n, s, [...f]]) })
    return c
  }
}
