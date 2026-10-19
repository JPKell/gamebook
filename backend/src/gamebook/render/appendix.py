"""Appendix HTML: one template per kind, plus a standalone document for previews.

Templates are autoescaped; author Markdown arrives pre-rendered as ``Markup`` from
``render.markdown`` (which escapes everything it doesn't produce itself).
"""

from __future__ import annotations

from functools import cache
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from gamebook.render.markdown import Resolver, to_html


@cache
def _env() -> Environment:
    return Environment(
        loader=PackageLoader("gamebook.render", "templates"),
        autoescape=select_autoescape(default=True, default_for_string=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def markdown(source: str, resolve: Resolver | None = None) -> Markup:
    return to_html(source, resolve)


def fragment(kind: str, title: str, data: dict[str, Any], *, codex: bool = False) -> str:
    """The appendix as an HTML fragment (a ``<section class="appendix">``)."""
    return _env().get_template(f"appendix/{kind}.html").render(title=title, codex=codex, **data)


def document(title: str, body: str) -> str:
    """A standalone page (styles inlined) for previews and the codex iframe."""
    return _env().get_template("document.html").render(title=title, body=Markup(body))
