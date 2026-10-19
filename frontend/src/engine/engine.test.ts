import { describe, expect, it } from 'vitest'

import { enemyStats } from './game'
import { type Env, evaluate, intOf, repr, boolOf } from './gbx/evaluate'
import { GbxSyntaxError, parse } from './gbx/parse'
import { SeededRng } from './gbx/pcg32'
import { Q } from './rational'

describe('rationals', () => {
  it('match Python Fraction for floor, mod and division', () => {
    expect(Q.of(7).div(Q.of(2)).floor()).toBe(3n)
    expect(Q.of(-7).div(Q.of(2)).floor()).toBe(-4n)
    expect(Q.of(7).mod(Q.of(-3)).eq(Q.of(-2))).toBe(true) // Python: 7 % -3 == -2
    expect(Q.of(-7).mod(Q.of(3)).eq(Q.of(2))).toBe(true)
    expect(Q.of(10, 4).eq(Q.of(5, 2))).toBe(true)
    expect(Q.of(-1, 2).ceil()).toBe(0n)
  })
})

const env = (vars: Record<string, number> = {}, stats: Record<string, number> = {}): Env => ({
  tiers: ['basic', 'medium'],
  currentTier: 'medium',
  variable: (n) => (n in vars ? Q.of(vars[n]!) : undefined),
  stat: (_o, k) => stats[k] ?? 0,
  ref: (f, k) => (f === 'has' ? k === 'rope' : f === 'count' ? 2 : false),
})

describe('gbx', () => {
  it('parses with Python precedence and limits', () => {
    expect(parse('1 + 2 * 3')).toEqual({
      t: 'bin',
      op: '+',
      l: { t: 'num', v: 1n },
      r: { t: 'bin', op: '*', l: { t: 'num', v: 2n }, r: { t: 'num', v: 3n } },
    })
    expect(() => parse('1 < 2 < 3')).toThrow(
      "Comparisons can't be chained; combine them with 'and' (at 6)",
    )
    expect(() => parse('2 +')).toThrow('Unexpected end of expression (at 3)')
    expect(() => parse('0d6')).toThrow(GbxSyntaxError)
    expect(() => parse('3 # 4')).toThrow("Unexpected character '#' (at 2)")
  })

  it('evaluates exactly, with Python equality and floor rounding', () => {
    expect(intOf('7 / 2', env(), null)).toBe(3)
    expect(intOf('-7 / 2', env(), null)).toBe(-4)
    expect(intOf('round(5 / 2) + floor(level / 3)', env({ level: 7 }), null)).toBe(5)
    expect(intOf('clamp(SKILL, 1, 10)', env({}, { SKILL: 14 }), null)).toBe(10)
    expect(boolOf('has(rope) and count(gold) == 2', env())).toBe(true)
    expect(boolOf('tier >= medium and not flag(x)', env())).toBe(true)
    expect(evaluate(parse('1 == true'), env(), null)).toBe(true) // Python: True == 1
    expect(() => intOf('4 / (2 - 2)', env(), null)).toThrow('division by zero')
    expect(() => boolOf('3', env())).toThrow('expected true/false, got 3')
    expect(() =>
      intOf(
        'nonsense',
        {
          ...env(),
          stat: () => {
            throw new Error('x')
          },
        },
        null,
      ),
    ).toThrow()
    expect(repr(Q.of(5, 2))).toBe('Fraction(5, 2)')
  })

  it('rolls dice from the shared PCG32 stream', () => {
    const rng = new SeededRng(7)
    const total = intOf('2d6 + 1', env(), rng)
    const [[n, sides, faces]] = rng.history as [[number, number, number[]]]
    expect([n, sides]).toEqual([2, 6])
    expect(total).toBe(faces[0]! + faces[1]! + 1)
  })
})

describe('review regressions', () => {
  it('keeps big integers exact and rejects results the player could not hold', () => {
    expect(intOf('9007199254740993 - 9007199254740992', env(), null)).toBe(1)
    const huge = '9'.repeat(400)
    expect(intOf(`${huge} - ${huge}`, env(), null)).toBe(0)
    expect(() => intOf('9007199254740993 * 2', env(), null)).toThrow('number too large')
  })

  it('accepts only ASCII digits and whitespace, like the Python lexer', () => {
    expect(() => parse('１２ + 1')).toThrow(GbxSyntaxError)
    expect(() => parse('1 +﻿2')).toThrow(GbxSyntaxError)
    expect(() => parse('1 +\x1c2')).toThrow("Unexpected character '\\x1c' (at 3)")
    expect(intOf('1 +\t\n2', env(), null)).toBe(3)
  })

  it('never reads inherited object properties as stats', () => {
    expect(enemyStats({}, 1, ['constructor', 'toString'], ['basic'], 'basic')).toEqual({
      constructor: 0,
      toString: 0,
    })
  })
})
