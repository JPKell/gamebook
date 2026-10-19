/**
 * Exact rationals over BigInt, matching Python's `fractions.Fraction` as the gbx
 * evaluator uses it: `/` is exact, `%` and `floor` round towards negative infinity.
 */
export class Q {
  readonly n: bigint
  readonly d: bigint

  private constructor(n: bigint, d: bigint) {
    this.n = n
    this.d = d
  }

  static of(n: bigint | number, d: bigint | number = 1n): Q {
    let num = BigInt(n)
    let den = BigInt(d)
    if (den === 0n) throw new RangeError('zero denominator')
    if (den < 0n) {
      num = -num
      den = -den
    }
    const g = gcd(num < 0n ? -num : num, den)
    return new Q(num / g, den / g)
  }

  add(o: Q): Q {
    return Q.of(this.n * o.d + o.n * this.d, this.d * o.d)
  }
  sub(o: Q): Q {
    return Q.of(this.n * o.d - o.n * this.d, this.d * o.d)
  }
  mul(o: Q): Q {
    return Q.of(this.n * o.n, this.d * o.d)
  }
  div(o: Q): Q {
    return Q.of(this.n * o.d, this.d * o.n)
  }
  /** Python `a % b`: the result has the sign of `b`. */
  mod(o: Q): Q {
    return this.sub(o.mul(this.div(o).floorQ()))
  }
  neg(): Q {
    return new Q(-this.n, this.d)
  }
  abs(): Q {
    return this.n < 0n ? this.neg() : this
  }
  cmp(o: Q): number {
    const l = this.n * o.d
    const r = o.n * this.d
    return l < r ? -1 : l > r ? 1 : 0
  }
  eq(o: Q): boolean {
    return this.n === o.n && this.d === o.d
  }
  isZero(): boolean {
    return this.n === 0n
  }
  /** Floor as a bigint. */
  floor(): bigint {
    const q = this.n / this.d
    return this.n < 0n && q * this.d !== this.n ? q - 1n : q
  }
  floorQ(): Q {
    return Q.of(this.floor())
  }
  ceil(): bigint {
    return -this.neg().floor()
  }
  /** Floor as a JS number (game values are small integers). */
  toInt(): number {
    return Number(this.floor())
  }
}

function gcd(a: bigint, b: bigint): bigint {
  while (b !== 0n) [a, b] = [b, a % b]
  return a === 0n ? 1n : a
}
