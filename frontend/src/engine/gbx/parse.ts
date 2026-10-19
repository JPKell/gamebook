/**
 * gbx tokenizer and Pratt parser: a line-for-line port of `core/gbx/lexer.py` and
 * `parser.py` (same grammar, limits and error messages).
 *
 * Precedence (low → high): `?:` (right-assoc), or, and, not,
 * `== != < <= > >=` (non-chaining), `+ -`, `* / %`, unary `-`, call / attribute / atom.
 */

export type Expr =
  | { t: 'num'; v: bigint }
  | { t: 'bool'; v: boolean }
  | { t: 'dice'; n: number; s: number }
  | { t: 'name'; n: string }
  | { t: 'attr'; o: string; a: string }
  | { t: 'call'; f: string; a: Expr[] }
  | { t: 'unary'; op: '-' | 'not'; x: Expr }
  | { t: 'bin'; op: '+' | '-' | '*' | '/' | '%' | 'and' | 'or'; l: Expr; r: Expr }
  | { t: 'cmp'; op: '==' | '!=' | '<' | '<=' | '>' | '>='; l: Expr; r: Expr }
  | { t: 'if'; c: Expr; y: Expr; n: Expr }

export class GbxSyntaxError extends Error {
  readonly reason: string
  readonly start: number
  constructor(reason: string, start: number) {
    super(`${reason} (at ${start})`)
    this.reason = reason
    this.start = start
  }
}

export class GbxEvalError extends Error {}

const KEYWORDS = new Set(['and', 'or', 'not', 'true', 'false'])
const MAX_DICE = 100
const MAX_SIDES = 1000
export const MAX_SOURCE_LENGTH = 2000
const MAX_DEPTH = 64
const COMPARE_OPS = new Set(['==', '!=', '<', '<=', '>', '>='])

type Kind = 'int' | 'dice' | 'ident' | 'kw' | 'op' | 'eof'
interface Token {
  kind: Kind
  text: string
  start: number
  end: number
}

// Same alternation order as the Python regex.
// ASCII only, like the Python lexer (re.ASCII): \s is exactly [ \t\n\r\f\v].
const TOKEN_RE =
  /(?<ws>[ \t\n\r\f\v]+)|(?<dice>(?:[0-9]+)?d[0-9]+)(?![A-Za-z0-9_])|(?<int>[0-9]+)(?![A-Za-z_])|(?<ident>[A-Za-z_][A-Za-z0-9_]*)|(?<op>==|!=|<=|>=|[-+*/%()<>,.?:])/y

const ESCAPES: Record<string, string> = { '\t': '\\t', '\n': '\\n', '\r': '\\r' }

/** Python repr() of a one-character string, for messages. */
function reprChar(c: string): string {
  if (c === "'") return `"'"`
  if (c === '\\') return "'\\\\'"
  const code = c.codePointAt(0)!
  if (ESCAPES[c]) return `'${ESCAPES[c]}'`
  if (code < 0x20 || (code >= 0x7f && code <= 0xa0) || code === 0xad)
    return `'\\x${code.toString(16).padStart(2, '0')}'`
  return `'${c}'`
}

export function tokenize(src: string): Token[] {
  const tokens: Token[] = []
  let pos = 0
  while (pos < src.length) {
    TOKEN_RE.lastIndex = pos
    const m = TOKEN_RE.exec(src)
    if (!m || !m.groups)
      throw new GbxSyntaxError(`Unexpected character ${reprChar(src[pos]!)}`, pos)
    const text = m[0]
    const start = pos
    pos += text.length
    const g = m.groups
    if (g.ws !== undefined) continue
    if (g.dice !== undefined) {
      const [countS, sidesS] = text.split('d') as [string, string]
      const count = countS ? Number(countS) : 1
      const sides = Number(sidesS)
      if (!(count >= 1 && count <= MAX_DICE))
        throw new GbxSyntaxError(`Dice count must be between 1 and ${MAX_DICE}`, start)
      if (!(sides >= 2 && sides <= MAX_SIDES))
        throw new GbxSyntaxError(`Dice must have between 2 and ${MAX_SIDES} sides`, start)
      tokens.push({ kind: 'dice', text, start, end: pos })
    } else if (g.int !== undefined) tokens.push({ kind: 'int', text, start, end: pos })
    else if (g.ident !== undefined)
      tokens.push({ kind: KEYWORDS.has(text) ? 'kw' : 'ident', text, start, end: pos })
    else tokens.push({ kind: 'op', text, start, end: pos })
  }
  tokens.push({ kind: 'eof', text: '', start: src.length, end: src.length })
  return tokens
}

function pyRepr(s: string): string {
  return s.includes("'") && !s.includes('"') ? `"${s}"` : `'${s.replace(/'/g, "\\'")}'`
}

class Parser {
  private tokens: Token[]
  private i = 0
  private depth = 0

  constructor(src: string) {
    this.tokens = tokenize(src)
  }

  private get tok(): Token {
    return this.tokens[this.i]!
  }
  private advance(): Token {
    return this.tokens[this.i++]!
  }
  private at(text: string): boolean {
    return (this.tok.kind === 'op' || this.tok.kind === 'kw') && this.tok.text === text
  }
  private describe(): string {
    return this.tok.kind === 'eof' ? 'end of expression' : pyRepr(this.tok.text)
  }
  private expect(text: string): Token {
    if (!this.at(text))
      throw new GbxSyntaxError(`Expected ${pyRepr(text)}, found ${this.describe()}`, this.tok.start)
    return this.advance()
  }
  private nest(): void {
    this.depth += 1
    if (this.depth > MAX_DEPTH)
      throw new GbxSyntaxError('Expression is nested too deeply', this.tok.start)
  }

  parse(): Expr {
    if (this.tok.kind === 'eof') throw new GbxSyntaxError('Empty expression', this.tok.start)
    const e = this.ternary()
    const rest = this.tokens[this.i]!
    if (rest.kind !== 'eof') throw new GbxSyntaxError(`Unexpected ${this.describe()}`, rest.start)
    return e
  }

  private ternary(): Expr {
    this.nest()
    let cond = this.or()
    if (this.at('?')) {
      this.advance()
      const y = this.ternary()
      this.expect(':')
      const n = this.ternary()
      cond = { t: 'if', c: cond, y, n }
    }
    this.depth -= 1
    return cond
  }

  private or(): Expr {
    let left = this.and()
    while (this.at('or')) {
      this.advance()
      left = { t: 'bin', op: 'or', l: left, r: this.and() }
    }
    return left
  }

  private and(): Expr {
    let left = this.not()
    while (this.at('and')) {
      this.advance()
      left = { t: 'bin', op: 'and', l: left, r: this.not() }
    }
    return left
  }

  private not(): Expr {
    if (this.at('not')) {
      this.advance()
      this.nest()
      const x = this.not()
      this.depth -= 1
      return { t: 'unary', op: 'not', x }
    }
    return this.compare()
  }

  private compare(): Expr {
    const left = this.additive()
    if (this.tok.kind === 'op' && COMPARE_OPS.has(this.tok.text)) {
      const op = this.advance().text as Extract<Expr, { t: 'cmp' }>['op']
      const right = this.additive()
      if (this.tok.kind === 'op' && COMPARE_OPS.has(this.tok.text))
        throw new GbxSyntaxError(
          "Comparisons can't be chained; combine them with 'and'",
          this.tok.start,
        )
      return { t: 'cmp', op, l: left, r: right }
    }
    return left
  }

  private additive(): Expr {
    let left = this.multiplicative()
    while (this.at('+') || this.at('-')) {
      const op = this.advance().text as '+' | '-'
      left = { t: 'bin', op, l: left, r: this.multiplicative() }
    }
    return left
  }

  private multiplicative(): Expr {
    let left = this.unary()
    while (this.at('*') || this.at('/') || this.at('%')) {
      const op = this.advance().text as '*' | '/' | '%'
      left = { t: 'bin', op, l: left, r: this.unary() }
    }
    return left
  }

  private unary(): Expr {
    if (this.at('-')) {
      this.advance()
      this.nest()
      const x = this.unary()
      this.depth -= 1
      return { t: 'unary', op: '-', x }
    }
    return this.atom()
  }

  private atom(): Expr {
    const t = this.tok
    if (t.kind === 'int') {
      this.advance()
      return { t: 'num', v: BigInt(t.text) } // exact, like Python ints
    }
    if (t.kind === 'dice') {
      this.advance()
      const [c, s] = t.text.split('d') as [string, string]
      return { t: 'dice', n: c ? Number(c) : 1, s: Number(s) }
    }
    if (t.kind === 'kw' && (t.text === 'true' || t.text === 'false')) {
      this.advance()
      return { t: 'bool', v: t.text === 'true' }
    }
    if (t.kind === 'ident') {
      this.advance()
      if (this.at('(')) return this.call(t)
      if (this.at('.')) {
        this.advance()
        const attr = this.tok
        if (attr.kind !== 'ident') throw new GbxSyntaxError("Expected a name after '.'", attr.start)
        this.advance()
        return { t: 'attr', o: t.text, a: attr.text }
      }
      return { t: 'name', n: t.text }
    }
    if (this.at('(')) {
      this.advance()
      const inner = this.ternary()
      this.expect(')')
      return inner
    }
    throw new GbxSyntaxError(`Unexpected ${this.describe()}`, t.start)
  }

  private call(name: Token): Expr {
    this.expect('(')
    const args: Expr[] = []
    if (!this.at(')')) {
      args.push(this.ternary())
      while (this.at(',')) {
        this.advance()
        args.push(this.ternary())
      }
    }
    this.expect(')')
    return { t: 'call', f: name.text, a: args }
  }
}

function children(e: Expr): Expr[] {
  switch (e.t) {
    case 'call':
      return e.a
    case 'unary':
      return [e.x]
    case 'bin':
    case 'cmp':
      return [e.l, e.r]
    case 'if':
      return [e.c, e.y, e.n]
    default:
      return []
  }
}

function depth(expr: Expr): number {
  let deepest = 0
  const stack: [Expr, number][] = [[expr, 1]]
  while (stack.length) {
    const [node, d] = stack.pop()!
    deepest = Math.max(deepest, d)
    for (const c of children(node)) stack.push([c, d + 1])
  }
  return deepest
}

const cache = new Map<string, Expr>()

/** Parse gbx source (cached). Throws GbxSyntaxError. */
export function parse(src: string): Expr {
  const hit = cache.get(src)
  if (hit) return hit
  if (src.length > MAX_SOURCE_LENGTH)
    throw new GbxSyntaxError(`Expression longer than ${MAX_SOURCE_LENGTH} characters`, 0)
  const expr = new Parser(src).parse()
  if (depth(expr) > MAX_DEPTH)
    throw new GbxSyntaxError('Expression is nested too deeply; split it up', 0)
  if (cache.size > 8192) cache.clear()
  cache.set(src, expr)
  return expr
}
