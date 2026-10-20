"""Imposition: blank padding, the back cover, and pages laid out on folded sheets."""

from __future__ import annotations

import io

from pypdf import PdfReader
from weasyprint import HTML

from gamebook.core.layout import Imposition
from gamebook.services.imposition import impose


def pages(n: int) -> bytes:
    body = "".join(
        f'<p style="break-after: page">P{i}</p>' if i < n else f"<p>P{i}</p>"
        for i in range(1, n + 1)
    )
    css = "@page { size: 100mm 150mm; margin: 10mm; }"
    data: bytes = HTML(string=f"<style>{css}</style>{body}").write_pdf()
    return data


def labels(page: object, width: float) -> tuple[str, str]:
    """The page labels on a sheet's left and right halves."""
    found: list[tuple[float, str]] = []

    def visit(text: str, cm: list[float], tm: list[float], *_: object) -> None:
        if text.strip():
            found.append((cm[4] + tm[4] * cm[0], text.strip()))

    page.extract_text(visitor_text=visit)  # type: ignore[attr-defined]
    left = "".join(t for x, t in found if x < width / 2) or "-"
    right = "".join(t for x, t in found if x >= width / 2) or "-"
    return left, right


def sides(data: bytes) -> list[tuple[str, str]]:
    reader = PdfReader(io.BytesIO(data))
    return [labels(p, float(p.mediabox.width)) for p in reader.pages]


def test_one_signature_booklet() -> None:
    out = impose(pages(8), Imposition(fold=True))
    assert (out.pages, out.blanks, out.sheets, out.signatures) == (8, 0, 2, 1)
    assert sides(out.pdf) == [("P8", "P1"), ("P2", "P7"), ("P6", "P3"), ("P4", "P5")]


def test_blanks_go_before_the_back_cover() -> None:
    out = impose(pages(6), Imposition(fold=True), back_cover_at=5)
    assert out.blanks == 2
    # Reading order: P1-P5, blank, blank, P6 (the back cover stays last).
    assert sides(out.pdf) == [("P6", "P1"), ("P2", "-"), ("-", "P3"), ("P4", "P5")]


def test_several_signatures() -> None:
    out = impose(pages(8), Imposition(fold=True, signature_pages=4))
    assert (out.sheets, out.signatures) == (2, 2)
    assert sides(out.pdf) == [("P4", "P1"), ("P2", "P3"), ("P8", "P5"), ("P6", "P7")]


def test_unfolded_signatures_only_pad() -> None:
    out = impose(pages(5), Imposition(signature_pages=8))
    reader = PdfReader(io.BytesIO(out.pdf))
    assert (len(reader.pages), out.blanks, out.sheets, out.signatures) == (8, 3, 0, 1)
    assert [p.extract_text().strip() for p in reader.pages] == [
        "P1", "P2", "P3", "P4", "P5", "", "", "",
    ]  # fmt: skip


def test_nothing_to_do() -> None:
    data = pages(3)
    out = impose(data, Imposition())
    assert out.pdf == data
    assert out.blanks == 0


def test_creep_moves_inner_sheets_towards_the_fold() -> None:
    plain = impose(pages(8), Imposition(fold=True, fold_marks=False)).pdf
    crept = impose(pages(8), Imposition(fold=True, fold_marks=False, creep_mm=2)).pdf

    def xs(data: bytes, side: int) -> list[float]:
        found: list[float] = []
        page = PdfReader(io.BytesIO(data)).pages[side]

        def visit(text: str, cm: list[float], tm: list[float], *_: object) -> None:
            if text.strip():
                found.append(cm[4] + tm[4] * cm[0])

        page.extract_text(visitor_text=visit)
        return sorted(found)

    assert xs(crept, 0) == xs(plain, 0)  # the outer sheet stays
    shift = 2 * 72 / 25.4
    inner_plain, inner_crept = xs(plain, 2), xs(crept, 2)
    assert abs(inner_crept[0] - (inner_plain[0] + shift)) < 0.5  # left page moves right
    assert abs(inner_crept[1] - (inner_plain[1] - shift)) < 0.5  # right page moves left
