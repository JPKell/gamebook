"""Print, preview and EPUB HTML for a compiled book (templates in ``templates/print``)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from markupsafe import Markup

from gamebook.core.art import PageSetup
from gamebook.core.layout import stylesheet
from gamebook.render.appendix import _env


def css(mode: str, setup: PageSetup, *, marks: bool = False, font_faces: str = "") -> str:
    """The stylesheet for print, the proof or EPUB. EPUB leaves the look to the reader."""
    name = {"print": "print.css", "screen": "screen.css", "epub": "epub.css"}[mode]
    s = {
        **setup.model_dump(),
        "inner_mm": round(setup.inner_mm, 2),
        "text_width": round(setup.text_width_mm, 2),
        "text_height": round(setup.text_height_mm, 2),
    }
    styles = (
        ""
        if mode == "epub"
        else stylesheet(
            styles=setup.styles,
            header=setup.header,
            footer=setup.footer,
            title_page=setup.title_page,
            sections=setup.sections,
            paged=mode == "print",
            font_faces=font_faces,
        )
    )
    return _env().get_template(f"print/{name}").render(s=s, marks=marks, styles=Markup(styles))


def document(
    *,
    title: str,
    series_title: str,
    tier_label: str,
    parts: list[dict[str, Any]],
    mode: str,
    setup: PageSetup,
    href: Callable[[int], str] = lambda n: f"#s{n}",
    anchor: Callable[[int], str] = lambda n: f"s{n}",
    css_href: str | None = None,
    xhtml: bool = False,
    marks: bool = False,
    font_faces: str = "",
) -> str:
    """The whole book (or one EPUB chunk of it) as an HTML document."""
    return (
        _env()
        .get_template("print/book.html")
        .render(
            title=title,
            series_title=series_title,
            tier_label=tier_label,
            parts=parts,
            mode=mode,
            css=Markup("" if css_href else css(mode, setup, marks=marks, font_faces=font_faces)),
            tp=setup.title_page,
            css_href=css_href,
            href=href,
            anchor=anchor,
            xhtml=xhtml,
        )
    )
