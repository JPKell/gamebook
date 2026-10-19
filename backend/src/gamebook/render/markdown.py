"""A small, safe Markdown subset for author pages (custom appendices, rules text).

Everything is HTML-escaped first; only this markup is produced: headings (# to ###),
paragraphs, bullet and numbered lists, **bold**, *italic*, horizontal rules, and
``[[mentions]]`` (rendered as the entity's name). No raw HTML, links or images,
so author text can't inject markup into print or the player.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable

from markupsafe import Markup

#: Mention → display name (None: show the key as written).
Resolver = Callable[[str | None, str], str | None]

_MENTION = re.compile(
    r"\[\[(?:(character|lore):)?([A-Za-z][A-Za-z0-9_]{0,63})(?:\|([^\]\n]*))?\]\]"
)


def _inline(text: str, resolve: Resolver | None) -> str:
    def mention(m: re.Match[str]) -> str:
        label = m.group(3)
        name = label or (resolve(m.group(1), m.group(2)) if resolve else None) or m.group(2)
        return f'<span class="mention">{html.escape(name)}</span>'

    parts: list[str] = []
    last = 0
    for m in _MENTION.finditer(text):
        parts.append(html.escape(text[last : m.start()]))
        parts.append(mention(m))
        last = m.end()
    parts.append(html.escape(text[last:]))
    out = "".join(parts)
    out = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", out)
    return re.sub(r"(?<![*\w])\*(?=\S)(.+?)(?<=\S)\*(?![*\w])", r"<em>\1</em>", out)


def to_html(source: str, resolve: Resolver | None = None) -> Markup:
    lines = (source or "").replace("\r\n", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []
    list_kind: str | None = None

    def flush_para() -> None:
        if para:
            out.append(f"<p>{_inline(' '.join(para), resolve)}</p>")
            para.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            out.append(f"</{list_kind}>")
            list_kind = None

    for raw in lines:
        line = raw.strip()
        if not line:
            flush_para()
            close_list()
            continue
        if m := re.match(r"^(#{1,3})\s+(.*)$", line):
            flush_para()
            close_list()
            level = len(m.group(1)) + 1  # page title is h1/h2: author headings start at h2
            out.append(f"<h{level}>{_inline(m.group(2), resolve)}</h{level}>")
            continue
        if re.match(r"^(-{3,}|\*{3,})$", line):
            flush_para()
            close_list()
            out.append("<hr>")
            continue
        bullet = re.match(r"^[-*]\s+(.*)$", line)
        number = re.match(r"^\d+[.)]\s+(.*)$", line)
        if bullet or number:
            flush_para()
            kind = "ul" if bullet else "ol"
            if list_kind != kind:
                close_list()
                out.append(f"<{kind}>")
                list_kind = kind
            item = (bullet or number).group(1)  # type: ignore[union-attr]
            out.append(f"<li>{_inline(item, resolve)}</li>")
            continue
        close_list()
        para.append(line)
    flush_para()
    close_list()
    return Markup("\n".join(out))
