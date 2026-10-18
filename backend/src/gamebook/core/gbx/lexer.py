"""gbx tokenizer."""

import re
from dataclasses import dataclass
from typing import Literal

from gamebook.core.gbx.ast import Span
from gamebook.core.gbx.errors import GbxSyntaxError

TokenKind = Literal["int", "dice", "ident", "kw", "op", "eof"]

KEYWORDS = frozenset({"and", "or", "not", "true", "false"})
MAX_DICE = 100
MAX_SIDES = 1000

_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<dice>(?:\d+)?d\d+)(?![A-Za-z0-9_])
  | (?P<int>\d+)(?![A-Za-z_])
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>==|!=|<=|>=|[-+*/%()<>,.?:])
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    span: Span


def tokenize(src: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    while pos < len(src):
        m = _TOKEN_RE.match(src, pos)
        if m is None:
            raise GbxSyntaxError(f"Unexpected character {src[pos]!r}", Span(pos, pos + 1))
        kind = m.lastgroup
        text = m.group()
        span = Span(m.start(), m.end())
        pos = m.end()
        if kind == "ws":
            continue
        if kind == "dice":
            count_s, sides_s = text.split("d")
            count = int(count_s) if count_s else 1
            sides = int(sides_s)
            if not 1 <= count <= MAX_DICE:
                raise GbxSyntaxError(f"Dice count must be between 1 and {MAX_DICE}", span)
            if not 2 <= sides <= MAX_SIDES:
                raise GbxSyntaxError(f"Dice must have between 2 and {MAX_SIDES} sides", span)
            tokens.append(Token("dice", text, span))
        elif kind == "int":
            tokens.append(Token("int", text, span))
        elif kind == "ident":
            tokens.append(Token("kw" if text in KEYWORDS else "ident", text, span))
        else:
            tokens.append(Token("op", text, span))
    tokens.append(Token("eof", "", Span(len(src), len(src))))
    return tokens
