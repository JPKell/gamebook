"""Extract and rename the keys an expression refers to."""

from __future__ import annotations

from dataclasses import dataclass

from gamebook.core.gbx.ast import Attr, Call, Expr, Name, Span, walk
from gamebook.core.gbx.parser import parse
from gamebook.core.gbx.scope import REF_FUNCTIONS, RefKind, Scope


@dataclass(frozen=True, slots=True)
class Reference:
    kind: RefKind
    key: str
    span: Span
    #: For STAT references, which object (``player``, ``enemy``…).
    obj: str | None = None
    #: The function used, for ref-function references (``has``, ``flag``…).
    func: str | None = None


def references(expr: Expr, scope: Scope) -> list[Reference]:
    """Every key the expression mentions, in source order."""
    out: list[Reference] = []
    ref_arg_spans: set[tuple[int, int]] = set()
    for node in walk(expr):
        if isinstance(node, Call) and node.func in REF_FUNCTIONS:
            fn = REF_FUNCTIONS[node.func]
            if len(node.args) == 1 and isinstance(node.args[0], Name):
                arg = node.args[0]
                ref_arg_spans.add((arg.span.start, arg.span.end))
                out.append(Reference(fn.kind, arg.name, arg.span, func=fn.name))
        elif isinstance(node, Attr):
            out.append(Reference(RefKind.STAT, node.attr, node.attr_span, obj=node.obj))
    for node in walk(expr):
        if not isinstance(node, Name) or (node.span.start, node.span.end) in ref_arg_spans:
            continue
        n = node.name
        if n in scope.variables:
            continue
        if n == "tier" or n in scope.tiers:
            if n != "tier":
                out.append(Reference(RefKind.TIER, n, node.span))
            continue
        if scope.bare_object is not None:
            out.append(Reference(RefKind.STAT, n, node.span, obj=scope.bare_object))
    out.sort(key=lambda r: r.span.start)
    return out


def rename_in_source(
    src: str, scope: Scope, kind: RefKind, old: str, new: str, *, obj: str | None = None
) -> str:
    """Rename every ``kind`` reference ``old`` → ``new``, preserving formatting.

    For stats, ``obj`` limits the rename to one object (e.g. only ``enemy.X``);
    None renames the stat on every object. Unparseable source is returned as-is.
    """
    try:
        expr = parse(src)
    except ValueError:
        return src
    spans = [
        r.span
        for r in references(expr, scope)
        if r.kind == kind and r.key == old and (obj is None or r.obj == obj)
    ]
    for span in sorted(spans, key=lambda s: s.start, reverse=True):
        src = src[: span.start] + new + src[span.end :]
    return src
