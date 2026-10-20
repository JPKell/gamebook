"""Signatures and folded sheets for a rendered PDF (``core.layout.Imposition``).

Blank pages fill the last signature (before the back cover, when there is one). When
sheets are folded, pages are laid two to a side in booklet order: print the result
double-sided, flipping on the short edge, fold each sheet and nest the sheets of a
signature.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

from gamebook.core.art import MM_PER_INCH
from gamebook.core.layout import Imposition, booklet_sides, padded_count

if TYPE_CHECKING:
    from pypdf import PageObject

PT_PER_MM = 72 / MM_PER_INCH
#: Fold marks: dashed, this long, at the middle of the sheet's top and bottom edges.
MARK_MM = 6.0


@dataclass
class Imposed:
    pdf: bytes
    #: Pages in reading order, before padding.
    pages: int
    blanks: int
    #: Physical sheets (folded only), and signatures.
    sheets: int
    signatures: int


def impose(data: bytes, imp: Imposition, *, back_cover_at: int | None = None) -> Imposed:
    """Pad to whole signatures and, when folding, lay pages out on sheets."""
    from pypdf import PageObject, PdfReader, PdfWriter, Transformation

    reader = PdfReader(io.BytesIO(data))
    n = len(reader.pages)
    total = padded_count(n, imp)
    blanks = total - n
    unit = imp.signature_pages or total
    signatures = total // unit if (imp.fold or imp.signature_pages) else 1
    at = back_cover_at if back_cover_at is not None and 0 < back_cover_at < n else n
    order: list[int | None] = [*range(at), *([None] * blanks), *range(at, n)]
    first = reader.pages[0]
    w, h = float(first.mediabox.width), float(first.mediabox.height)

    if not imp.fold:
        if not blanks:
            return Imposed(data, n, 0, 0, signatures)
        writer = PdfWriter()
        writer.append(reader)
        for _ in range(blanks):
            blank = writer.insert_blank_page(w, h, at)
            # Same boxes as the rendered pages (printers check the trim).
            blank.trimbox = first.trimbox
            blank.bleedbox = first.bleedbox
        out = io.BytesIO()
        writer.write(out)
        return Imposed(out.getvalue(), n, blanks, 0, signatures)

    writer = PdfWriter()
    marks = _fold_marks(2 * w, h) if imp.fold_marks else None
    per_sig = unit // 4
    creep = imp.creep_mm * PT_PER_MM
    for k, (left, right) in enumerate(booklet_sides(total, imp.signature_pages)):
        # Sheet k // 2 of its signature: inner sheets creep towards the fold.
        sheet_no = (k // 2) % per_sig
        shift = creep * sheet_no / max(1, per_sig - 1)
        sheet = PageObject.create_blank_page(width=2 * w, height=h)
        for idx, x in ((left, shift), (right, w - shift)):
            src = order[idx]
            if src is not None:
                sheet.merge_transformed_page(
                    reader.pages[src], Transformation().translate(tx=x, ty=0)
                )
        if marks is not None:
            sheet.merge_page(marks)
        writer.add_page(sheet)
    out = io.BytesIO()
    writer.write(out)
    return Imposed(out.getvalue(), n, blanks, total // 4, signatures)


def _fold_marks(width: float, height: float) -> PageObject:
    """A transparent page with short fold lines at the middle of the top and bottom edges."""
    import pydyf
    from pypdf import PdfReader

    mark = MARK_MM * PT_PER_MM
    x = width / 2
    s = pydyf.Stream()
    s.set_line_width(0.3)
    s.set_color_rgb(0.4, 0.4, 0.4, stroke=True)
    s.set_dash([2, 2], 0)
    s.move_to(x, 0)
    s.line_to(x, mark)
    s.move_to(x, height - mark)
    s.line_to(x, height)
    s.stroke()
    pdf = pydyf.PDF()
    pdf.add_object(s)
    pdf.add_page(
        pydyf.Dictionary(
            {
                "Type": "/Page",
                "Parent": pdf.pages.reference,
                "MediaBox": pydyf.Array([0, 0, width, height]),
                "Contents": s.reference,
                "Resources": pydyf.Dictionary({}),
            }
        )
    )
    buf = io.BytesIO()
    pdf.write(buf)
    return PdfReader(io.BytesIO(buf.getvalue())).pages[0]
