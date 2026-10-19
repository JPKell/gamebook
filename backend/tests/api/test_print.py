"""Phase 11 API: numbering, the print compiler, proof, verification, PDF and EPUB."""

from __future__ import annotations

import io
import time
import zipfile
from collections.abc import Callable
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient

from gamebook.config import Settings

from .conftest import Api, Json
from .test_art import png, upload
from .test_playtest import playable

__all__ = ["playable"]


def wait_job(api: Api, job_id: str, timeout: float = 120) -> Json:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job: Json = api.get(f"/jobs/{job_id}")
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.1)
    raise AssertionError("job still running")


def numbers(api: Api, book_id: str, tier: str = "basic") -> dict[str, int]:
    pre = api.get(f"/books/{book_id}/print/preflight?tier={tier}")
    return {f"{r['title']}:{r['kind']}": r["number"] for r in pre["numbers"]}


def test_numbering_is_stable_pinned_and_reshufflable(
    api: Api,
    playable: Json,
) -> None:
    bid = playable["book_id"]
    first = numbers(api, bid)
    assert first["Start:section"] == 1  # the start is section 1
    assert sorted(first.values()) == list(range(1, len(first) + 1))
    assert numbers(api, bid) == first  # stable

    # A new section doesn't renumber the others.
    act = api.get(f"/books/{bid}/graph")["acts"][0]["id"]
    api.post(f"/books/{bid}/nodes", {"act_id": act, "title": "Annex"})
    after = numbers(api, bid)
    assert {k: v for k, v in after.items() if k in first} == first

    # Pins hold; a pin outside the range is reported, not applied.
    api.patch(f"/nodes/{playable['dead']}", {"section_pin": 2})
    assert numbers(api, bid)["Dead:section"] == 2
    api.patch(f"/nodes/{playable['treasure']}", {"section_pin": 99})
    pre = api.get(f"/books/{bid}/print/preflight?tier=basic")
    assert [w["code"] for w in pre["warnings"] if w["code"] == "pin_ignored"] == ["pin_ignored"]

    seed = api.post(f"/books/{bid}/print/reshuffle", {"seed": 4242}, expect=200)["seed"]
    assert seed == 4242
    shuffled = numbers(api, bid)
    assert (shuffled["Start:section"], shuffled["Dead:section"]) == (1, 2)


def test_proof_phrases_the_mechanics_for_the_edition(
    api: Api,
    series: Json,
    playable: Json,
) -> None:
    bid = playable["book_id"]
    # A section with two text variants gets a router.
    v = api.post(
        f"/nodes/{playable['start']}/variants",
        {"label": "Roped", "condition": "has(rope)", "priority": 5},
    )
    api.post(
        f"/variants/{v['id']}/prose", {"text": "The rope holds.\n\nYou climb.", "approve": True}
    )
    html = api.c.get(f"/api/books/{bid}/print/preview", params={"tier": "basic"})
    assert html.headers["content-type"].startswith("text/html")
    assert "script-src 'none'" in html.headers["content-security-policy"]
    text = html.text
    assert "If you have the Rope, turn to" in text
    assert "Otherwise, turn to" in text
    assert "The rope holds." in text
    assert "ORC" in text
    assert "If you win, turn to" in text
    assert "you succeed if" in text
    assert "Your Character" in text
    assert "Adventure Sheet" in text
    assert "Now turn to section" in text

    pre = api.get(f"/books/{bid}/print/preflight?tier=basic")
    assert pre["routers"] == 1
    assert pre["drafts"] >= 1  # sections without approved prose print their notes
    assert any(w["code"] == "no_prose" for w in pre["warnings"])


def test_proof_explains_levels_class_bonuses_and_gear(
    api: Api,
    series: Json,
    playable: Json,
) -> None:
    bid = playable["book_id"]
    text = api.c.get(f"/api/books/{bid}/print/preview", params={"tier": "medium"}).text
    assert "<strong>Experience.</strong> Whenever you win a fight, add" in text
    assert "the enemy&#39;s level" in text
    assert 'ORC <span class="level">(level 1)</span>' in text
    basic = api.c.get(f"/api/books/{bid}/print/preview", params={"tier": "basic"}).text
    assert "Experience." not in basic
    assert "(level 1)" not in basic

    rs = api.get(f"/series/{series['id']}/rule-systems")[0]
    definition = rs["definition"]
    definition["tiers"][0]["starting_items"] = [{"item": "rope", "qty": 2}]
    api.patch(f"/rule-systems/{rs['id']}", {"definition": definition})
    text = api.c.get(f"/api/books/{bid}/print/preview", params={"tier": "advanced"}).text
    assert "Add 1 to your Skill and to your maximum Skill" in text  # the Ranger
    assert "You start with: 2 x Rope." in text


def test_verify_bot_proves_the_print_edition(
    api: Api,
    playable: Json,
) -> None:
    r = api.post(
        f"/books/{playable['book_id']}/print/verify", {"tier": "basic", "runs": 60}, expect=200
    )
    assert r["ok"], r
    assert r["moves"] >= r["runs"] == 60
    assert r["structure"] == []


def test_pdf_and_epub_exports(
    api: Api,
    series: Json,
    playable: Json,
    graph: Callable[[], Json],
) -> None:
    bid = playable["book_id"]
    a = upload(api, series["id"], png(1200, 900))
    api.patch(f"/assets/{a['id']}", {"alt_text": "An orc on a bridge"})
    api.post(
        "/placements",
        {
            "target_type": "node",
            "target_id": playable["start"],
            "asset_id": a["id"],
            "media": "both",
        },
    )
    api.post(
        "/placements",
        {"target_type": "book", "target_id": bid, "role": "cover_front", "asset_id": a["id"]},
    )
    api.post(f"/books/{bid}/appendices", {"kind": "bestiary"})

    job = api.post(f"/books/{bid}/print/exports", {"tier": "basic", "format": "pdf"})
    done = wait_job(api, job["id"])
    assert done["status"] == "done", done
    assert done["result"]["pages"] >= 5
    pdf = api.c.get(f"/api/print/exports/{job['id']}")
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert "attachment" in pdf.headers["content-disposition"]

    job = api.post(f"/books/{bid}/print/exports", {"tier": "basic", "format": "epub"})
    assert wait_job(api, job["id"])["status"] == "done"
    data = api.c.get(f"/api/print/exports/{job['id']}").content
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        assert names[0] == "mimetype"
        assert z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert z.read("mimetype") == b"application/epub+zip"
        assert any(n.startswith("OEBPS/images/") for n in names)
        for n in names:  # every document is well-formed XML
            if n.endswith((".xhtml", ".opf", ".xml")):
                ET.fromstring(z.read(n))
        sections = "".join(z.read(n).decode() for n in names if "sections-" in n)
        assert 'href="sections-001.xhtml#s' in sections
        assert 'alt="An orc on a bridge"' in sections

    api.get(f"/print/exports/{playable['book_id']}", expect=404)
    api.post(f"/books/{bid}/print/exports", {"tier": "nope", "format": "pdf"}, expect=422)


# ── review regressions ────────────────────────────────────────────────────


def _epub(api: Api, book_id: str, tier: str) -> zipfile.ZipFile:
    job = api.post(f"/books/{book_id}/print/exports", {"tier": tier, "format": "epub"})
    assert wait_job(api, job["id"])["status"] == "done"
    return zipfile.ZipFile(io.BytesIO(api.c.get(f"/api/print/exports/{job['id']}").content))


def test_epub_editions_have_their_own_identifier_and_no_broken_images(
    api: Api,
    series: Json,
    settings: Settings,
    playable: Json,
) -> None:
    bid = playable["book_id"]
    a = upload(api, series["id"], png(300, 200))
    api.post(
        "/placements", {"target_type": "node", "target_id": playable["start"], "asset_id": a["id"]}
    )
    (settings.data_dir / "assets" / f"{a['sha256']}.png").unlink()  # the file went missing
    ids = []
    for tier in ("basic", "advanced"):
        with _epub(api, bid, tier) as z:
            opf = z.read("OEBPS/content.opf").decode()
            ids.append(opf.split('<dc:identifier id="bookid">')[1].split("<")[0])
            docs = "".join(z.read(n).decode() for n in z.namelist() if n.endswith(".xhtml"))
            assert "images/" not in docs  # a placeholder, not a dangling link
    assert ids[0] != ids[1]


def test_proof_prints_sold_out_and_the_real_start(
    api: Api,
    series: Json,
    playable: Json,
) -> None:
    bid = playable["book_id"]
    rope = next(i for i in api.get(f"/series/{series['id']}/items") if i["key"] == "rope")
    api.put(
        f"/nodes/{playable['start']}/shop",
        {"items": [{"item_id": rope["id"], "price": 2, "stock": 0}]},
    )
    api.patch(f"/nodes/{playable['dead']}", {"section_pin": 1})
    text = api.c.get(f"/api/books/{bid}/print/preview", params={"tier": "basic"}).text
    assert "Sold out" in text
    start = numbers(api, bid)["Start:section"]
    assert start != 1
    assert f'Now turn to section <a class="turn" href="#s{start}">{start}</a>' in text


def test_numbering_survives_an_export_round_trip(
    api: Api,
    client: TestClient,
    series: Json,
    playable: Json,
) -> None:
    bid = playable["book_id"]
    api.post(f"/books/{bid}/print/reshuffle", {"seed": 777}, expect=200)
    before = numbers(api, bid)
    zipped = client.get(f"/api/series/{series['id']}/export.zip").content
    res = client.post(
        "/api/import",
        content=zipped,
        params={"replace": True},
        headers={"Content-Type": "application/zip"},
    )
    assert res.status_code == 201, res.text
    assert numbers(api, bid) == before
    assert api.get(f"/books/{bid}/print/preflight?tier=basic")["seed"] == 777
