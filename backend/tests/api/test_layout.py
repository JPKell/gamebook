"""Print layout API: page setup with styles and running heads, fonts, signatures, folding."""

from __future__ import annotations

import io
from typing import Any

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from pypdf import PdfReader

from .conftest import Api, Json
from .test_playtest import playable
from .test_print import wait_job

__all__ = ["playable"]

MM = 72 / 25.4


def make_font(family: str, *, italic: bool = False) -> bytes:
    """A TrueType font with a box glyph for every printable ASCII character."""
    chars = [chr(c) for c in range(32, 127)]
    names = [".notdef"] + [f"g{ord(c)}" for c in chars]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({ord(c): f"g{ord(c)}" for c in chars})
    pen = TTGlyphPen(None)
    pen.moveTo((50, 0))
    pen.lineTo((50, 700))
    pen.lineTo((450, 700))
    pen.lineTo((450, 0))
    pen.closePath()
    box = pen.glyph()
    fb.setupGlyf(dict.fromkeys(names, box))
    fb.setupHorizontalMetrics(dict.fromkeys(names, (500, 50)))
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    style = "Italic" if italic else "Regular"
    fb.setupNameTable({"familyName": family, "styleName": style})
    fb.setupOS2(usWeightClass=400, fsSelection=0x01 if italic else 0x40)
    fb.setupPost()
    out = io.BytesIO()
    fb.save(out)
    return out.getvalue()


def setup_body(api: Api, book_id: str, **changes: Any) -> Json:
    page: Json = api.get(f"/books/{book_id}/page-setup")
    for k in ("text_width", "text_height", "roles"):
        page.pop(k)
    return {**page, **changes}


def export_pdf(api: Api, book_id: str, **kw: Any) -> tuple[Json, PdfReader]:
    job = api.post(f"/books/{book_id}/print/exports", {"tier": "basic", "format": "pdf", **kw})
    done = wait_job(api, job["id"])
    assert done["status"] == "done", done
    data = api.c.get(f"/api/print/exports/{job['id']}").content
    return done["result"], PdfReader(io.BytesIO(data))


def test_page_setup_round_trips_the_layout(api: Api, book: Json) -> None:
    bid = book["id"]
    page = api.get(f"/books/{bid}/page-setup")
    roles = {r["key"]: r for r in page["roles"]}
    assert roles["section"]["default"]["size_pt"] == 15
    assert roles["footer"]["label"] == "Running footer"
    assert page["footer"]["verso"]["center"] == "page"

    saved = api.put(
        f"/books/{bid}/page-setup",
        setup_body(
            api,
            bid,
            gutter_mm=5,
            styles={"body": {"font": "DejaVu Serif", "size_pt": 11}, "turn": {"italic": True}},
            header={"recto": {"right": "section_last"}, "text": "", "gap_mm": 3},
            title_page={"subtitle": "A Test", "byline": "By Someone", "show_series": False},
            sections={"divider": "asterism", "keep_together": True},
        ),
    )
    assert saved["gutter_mm"] == 5
    assert saved["text_width"] == pytest.approx(page["text_width"] - 5, abs=0.1)
    again = api.get(f"/books/{bid}/page-setup")
    assert again["styles"]["body"]["font"] == "DejaVu Serif"
    assert again["styles"]["turn"] == {**dict.fromkeys(again["styles"]["body"]), "italic": True}
    assert again["header"]["recto"]["right"] == "section_last"
    assert again["sections"]["divider"] == "asterism"


@pytest.mark.parametrize(
    "change",
    [
        {"styles": {"body": {"font": 'x"; } * { color: red'}}},
        {"styles": {"body": {"color": "red"}}},
        {"imposition": {"signature_pages": 6}},
        {"header": {"verso": {"left": "everything"}}},
        {"gutter_mm": 60},
    ],
)
def test_page_setup_rejects_bad_layouts(api: Api, book: Json, change: Json) -> None:
    api.put(f"/books/{book['id']}/page-setup", setup_body(api, book["id"], **change), expect=422)


def test_gutter_counts_against_the_text_block(api: Api, book: Json) -> None:
    body = setup_body(api, book["id"], gutter_mm=40, margin_inner_mm=50, margin_outer_mm=50)
    api.put(f"/books/{book['id']}/page-setup", body, expect=422)


def test_folding_sets_the_page_size(api: Api, book: Json) -> None:
    saved = api.put(
        f"/books/{book['id']}/page-setup",
        setup_body(
            api,
            book["id"],
            imposition={"fold": True, "sheet_width_mm": 297, "sheet_height_mm": 210},
        ),
    )
    assert (saved["trim_width_mm"], saved["trim_height_mm"]) == (148.5, 210)


def test_the_proof_uses_the_layout(api: Api, playable: Json) -> None:
    bid = playable["book_id"]
    api.put(
        f"/books/{bid}/page-setup",
        setup_body(
            api,
            bid,
            styles={"section": {"font": "DejaVu Sans", "color": "#aa0000"}},
            title_page={
                "subtitle": "Into the Dark",
                "byline": "by A. Writer",
                "show_edition": False,
            },
        ),
    )
    html = api.c.get(f"/api/books/{bid}/print/preview", params={"tier": "basic"}).text
    assert '"DejaVu Sans", serif' in html
    assert "#aa0000" in html
    assert '<p class="subtitle">Into the Dark</p>' in html
    assert '<p class="byline">by A. Writer</p>' in html
    assert 'class="edition"' not in html


def test_running_heads_print(api: Api, playable: Json, book: Json) -> None:
    bid = playable["book_id"]
    api.put(
        f"/books/{bid}/page-setup",
        setup_body(
            api,
            bid,
            header={
                "verso": {"left": "title"},
                "recto": {"right": "text"},
                "text": "Running Head",
            },
        ),
    )
    _, pdf = export_pdf(api, bid)
    texts = [p.extract_text() for p in pdf.pages]
    assert "Running Head" not in texts[0]  # never on the title page
    assert any("Running Head" in t for t in texts[1:])
    assert any(t.strip().startswith(book["title"]) for t in texts[1:])


def test_signatures_pad_with_blank_pages(api: Api, playable: Json) -> None:
    bid = playable["book_id"]
    plain, pdf = export_pdf(api, bid)
    n = plain["pages"]
    assert len(pdf.pages) == n
    assert plain["blanks"] == 0
    assert plain["sheets"] == 0

    api.put(f"/books/{bid}/page-setup", setup_body(api, bid, imposition={"signature_pages": 16}))
    padded, pdf = export_pdf(api, bid)
    assert padded["pages"] == n
    assert len(pdf.pages) % 16 == 0
    assert padded["blanks"] == len(pdf.pages) - n
    assert padded["signatures"] == len(pdf.pages) // 16

    # Reading order on request: no padding.
    _, pdf = export_pdf(api, bid, imposed=False)
    assert len(pdf.pages) == n


def test_folded_sheets(api: Api, playable: Json) -> None:
    bid = playable["book_id"]
    api.put(
        f"/books/{bid}/page-setup",
        setup_body(
            api,
            bid,
            imposition={
                "fold": True,
                "sheet_width_mm": 215.9,
                "sheet_height_mm": 279.4,
                "signature_pages": 8,
                "creep_mm": 0.5,
            },
        ),
    )
    result, pdf = export_pdf(api, bid)
    total = result["pages"] + result["blanks"]
    assert total % 8 == 0
    assert result["sheets"] == total // 4
    assert result["signatures"] == total // 8
    assert len(pdf.pages) == result["sheets"] * 2  # two sides per sheet
    box = pdf.pages[0].mediabox
    assert float(box.width) == pytest.approx(279.4 * MM, abs=0.5)  # landscape sheet
    assert float(box.height) == pytest.approx(215.9 * MM, abs=0.5)
    assert result["file"].endswith("-sheets.pdf")

    # The pages on their own, in reading order, at half the sheet (with bleed and marks).
    single, pdf = export_pdf(api, bid, imposed=False)
    assert len(pdf.pages) == single["pages"]
    assert float(pdf.pages[1].trimbox.width) == pytest.approx(139.7 * MM, abs=0.5)


def test_sample_pdf(api: Api, playable: Json) -> None:
    bid = playable["book_id"]
    res = api.c.get(f"/api/books/{bid}/print/sample", params={"tier": "basic"})
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"] == "inline"
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(res.content)).pages)
    assert "ORC" in text  # the sample includes a fight

    api.put(f"/books/{bid}/page-setup", setup_body(api, bid, imposition={"fold": True}))
    res = api.c.get(f"/api/books/{bid}/print/sample", params={"tier": "basic", "imposed": True})
    box = PdfReader(io.BytesIO(res.content)).pages[0].mediabox
    assert float(box.width) > float(box.height)


def test_uploaded_fonts(api: Api, playable: Json) -> None:
    bid = playable["book_id"]
    res = api.c.post("/api/print/fonts", content=make_font("Gamebook Test"))
    assert res.status_code == 201, res.text
    font = res.json()
    assert (font["family"], font["weight"], font["italic"]) == ("Gamebook Test", 400, False)
    api.c.post("/api/print/fonts", content=make_font("Gamebook Test", italic=True))
    listed = api.get("/print/fonts")
    assert [(f["family"], f["italic"]) for f in listed["uploaded"]] == [
        ("Gamebook Test", False),
        ("Gamebook Test", True),
    ]
    assert "serif" in listed["generic"]

    bad = api.c.post("/api/print/fonts", content=b"not a font at all")
    assert bad.status_code == 422

    served = api.c.get(f"/api/print/fonts/{font['file']}")
    assert served.headers["content-type"] == "font/ttf"
    assert served.headers["access-control-allow-origin"] == "*"
    api.get("/print/fonts/../../etc/passwd", expect=404)
    api.get(f"/print/fonts/{'0' * 64}.ttf", expect=404)

    api.put(
        f"/books/{bid}/page-setup",
        setup_body(api, bid, styles={"section": {"font": "Gamebook Test"}}),
    )
    html = api.c.get(f"/api/books/{bid}/print/preview", params={"tier": "basic"}).text
    assert f'src: url("/api/print/fonts/{font["file"]}")' in html
    _, pdf = export_pdf(api, bid)
    fonts = set()
    for p in pdf.pages:
        resources: Any = p["/Resources"]
        for f in (resources.get("/Font") or {}).values():
            fonts.add(str(f.get_object().get("/BaseFont")))
    assert any("Gamebook" in f for f in fonts), fonts

    api.delete(f"/print/fonts/{font['id']}")
    api.delete(f"/print/fonts/{font['id']}", expect=404)
    assert len(api.get("/print/fonts")["uploaded"]) == 1


def test_folding_a_huge_sheet_is_a_422(api: Api, book: Json) -> None:
    body = setup_body(
        api,
        book["id"],
        imposition={"fold": True, "sheet_width_mm": 1200, "sheet_height_mm": 1000},
    )
    api.put(f"/books/{book['id']}/page-setup", body, expect=422)


def test_the_sample_drops_later_acts() -> None:
    from gamebook.core.printbook.compile import Block
    from gamebook.services.printing import SAMPLE_SECTIONS, _sample

    def section(n: int, fight: bool = False) -> Json:
        blocks = [Block("choice", {"fight": {"enemies": []}})] if fight else []
        return {"kind": "section", "section": {"number": n, "blocks": blocks}}

    parts: list[Json] = [{"kind": "title"}, {"kind": "html"}, {"kind": "act", "index": 0}]
    parts += [section(n) for n in range(1, SAMPLE_SECTIONS + 3)]
    parts += [{"kind": "act", "index": 1}, section(50, fight=True), {"kind": "act", "index": 2}]
    parts += [section(60), {"kind": "html"}, {"kind": "art", "back_cover": True}]
    out = _sample(parts)
    assert [p["kind"] for p in out].count("act") == 1
    numbers = [p["section"]["number"] for p in out if p["kind"] == "section"]
    assert numbers == [*range(1, SAMPLE_SECTIONS + 1), 50]  # plus the first fight
    assert out[-1]["kind"] == "section"
