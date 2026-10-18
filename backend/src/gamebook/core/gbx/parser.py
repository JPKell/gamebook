"""gbx Pratt parser.

Precedence (low → high)::

    ?:  (right-assoc)   or   and   not   == != < <= > >= (non-chaining)
    + -   * / %   unary -   call / attribute / atom
"""

from gamebook.core.gbx.ast import (
    Attr,
    Binary,
    Bool,
    Call,
    Compare,
    Dice,
    Expr,
    Name,
    Num,
    Span,
    Ternary,
    Unary,
    children,
)
from gamebook.core.gbx.errors import GbxSyntaxError
from gamebook.core.gbx.lexer import Token, tokenize

MAX_SOURCE_LENGTH = 2000
MAX_DEPTH = 64

_COMPARE_OPS = frozenset({"==", "!=", "<", "<=", ">", ">="})


class _Parser:
    def __init__(self, src: str) -> None:
        self.tokens = tokenize(src)
        self.i = 0
        self.depth = 0

    # ── helpers ──
    @property
    def tok(self) -> Token:
        return self.tokens[self.i]

    def advance(self) -> Token:
        t = self.tokens[self.i]
        self.i += 1
        return t

    def at(self, text: str) -> bool:
        return self.tok.kind in ("op", "kw") and self.tok.text == text

    def expect(self, text: str) -> Token:
        if not self.at(text):
            raise GbxSyntaxError(f"Expected {text!r}, found {self._describe()}", self.tok.span)
        return self.advance()

    def _describe(self) -> str:
        return "end of expression" if self.tok.kind == "eof" else repr(self.tok.text)

    # ── grammar ──
    def parse(self) -> Expr:
        if self.tok.kind == "eof":
            raise GbxSyntaxError("Empty expression", self.tok.span)
        e = self.ternary()
        rest = self.tokens[self.i]
        if rest.kind != "eof":
            raise GbxSyntaxError(f"Unexpected {self._describe()}", rest.span)
        return e

    def ternary(self) -> Expr:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise GbxSyntaxError("Expression is nested too deeply", self.tok.span)
        cond = self.or_()
        if self.at("?"):
            self.advance()
            then = self.ternary()
            self.expect(":")
            otherwise = self.ternary()
            cond = Ternary(cond, then, otherwise, Span(cond.span.start, otherwise.span.end))
        self.depth -= 1
        return cond

    def or_(self) -> Expr:
        left = self.and_()
        while self.at("or"):
            self.advance()
            right = self.and_()
            left = Binary("or", left, right, Span(left.span.start, right.span.end))
        return left

    def and_(self) -> Expr:
        left = self.not_()
        while self.at("and"):
            self.advance()
            right = self.not_()
            left = Binary("and", left, right, Span(left.span.start, right.span.end))
        return left

    def _nest(self) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise GbxSyntaxError("Expression is nested too deeply", self.tok.span)

    def not_(self) -> Expr:
        if self.at("not"):
            start = self.advance().span.start
            self._nest()
            operand = self.not_()
            self.depth -= 1
            return Unary("not", operand, Span(start, operand.span.end))
        return self.compare()

    def compare(self) -> Expr:
        left = self.additive()
        if self.tok.kind == "op" and self.tok.text in _COMPARE_OPS:
            op = self.advance().text
            right = self.additive()
            if self.tok.kind == "op" and self.tok.text in _COMPARE_OPS:
                raise GbxSyntaxError(
                    "Comparisons can't be chained; combine them with 'and'", self.tok.span
                )
            return Compare(op, left, right, Span(left.span.start, right.span.end))  # type: ignore[arg-type]
        return left

    def additive(self) -> Expr:
        left = self.multiplicative()
        while self.at("+") or self.at("-"):
            op = self.advance().text
            right = self.multiplicative()
            left = Binary(op, left, right, Span(left.span.start, right.span.end))  # type: ignore[arg-type]
        return left

    def multiplicative(self) -> Expr:
        left = self.unary()
        while self.at("*") or self.at("/") or self.at("%"):
            op = self.advance().text
            right = self.unary()
            left = Binary(op, left, right, Span(left.span.start, right.span.end))  # type: ignore[arg-type]
        return left

    def unary(self) -> Expr:
        if self.at("-"):
            start = self.advance().span.start
            self._nest()
            operand = self.unary()
            self.depth -= 1
            return Unary("-", operand, Span(start, operand.span.end))
        return self.atom()

    def atom(self) -> Expr:
        t = self.tok
        if t.kind == "int":
            self.advance()
            return Num(int(t.text), t.span)
        if t.kind == "dice":
            self.advance()
            count_s, sides_s = t.text.split("d")
            return Dice(int(count_s) if count_s else 1, int(sides_s), t.span)
        if t.kind == "kw" and t.text in ("true", "false"):
            self.advance()
            return Bool(t.text == "true", t.span)
        if t.kind == "ident":
            self.advance()
            if self.at("("):
                return self.call(t)
            if self.at("."):
                self.advance()
                attr = self.tok
                if attr.kind != "ident":
                    raise GbxSyntaxError("Expected a name after '.'", attr.span)
                self.advance()
                return Attr(t.text, attr.text, Span(t.span.start, attr.span.end), attr.span)
            return Name(t.text, t.span)
        if self.at("("):
            self.advance()
            inner = self.ternary()
            self.expect(")")
            return inner
        raise GbxSyntaxError(f"Unexpected {self._describe()}", t.span)

    def call(self, name: Token) -> Expr:
        self.expect("(")
        args: list[Expr] = []
        if not self.at(")"):
            args.append(self.ternary())
            while self.at(","):
                self.advance()
                args.append(self.ternary())
        end = self.expect(")").span.end
        return Call(name.text, tuple(args), Span(name.span.start, end))


def parse(src: str) -> Expr:
    """Parse gbx source. Raises :class:`GbxSyntaxError`."""
    if len(src) > MAX_SOURCE_LENGTH:
        raise GbxSyntaxError(
            f"Expression longer than {MAX_SOURCE_LENGTH} characters", Span(0, len(src))
        )
    expr = _Parser(src).parse()
    if ast_depth(expr) > MAX_DEPTH:
        raise GbxSyntaxError("Expression is nested too deeply; split it up", Span(0, len(src)))
    return expr


def ast_depth(expr: Expr) -> int:
    """Depth of the tree, computed iteratively (safe on degenerate inputs)."""
    deepest = 0
    stack: list[tuple[Expr, int]] = [(expr, 1)]
    while stack:
        node, d = stack.pop()
        deepest = max(deepest, d)
        stack.extend((c, d + 1) for c in children(node))
    return deepest
