"""Phase 10 API: the asset library, placements, page setup, maps, appendices and export."""

from __future__ import annotations

import hashlib
import io
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from PIL import Image

from gamebook.config import Settings
from gamebook.export import tree

from .conftest import Api, Json
from .test_playtest import playable

__all__ = ["playable"]


def png(width: int, height: int, color: tuple[int, int, int] = (200, 30, 30)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), color).save(out, "PNG")
    return out.getvalue()


def upload(api: Api, series_id: str, data: bytes, name: str = "art.png", expect: int = 201) -> Json:
    res = api.c.post(
        f"/api/series/{series_id}/assets",
        content=data,
        params={"filename": name},
        headers={"Content-Type": "image/png"},
    )
    assert res.status_code == expect, res.text
    out: Json = res.json()
    return out


def problems(api: Api, book_id: str, prefix: str = "") -> list[Json]:
    return [
        p
        for p in api.get(f"/books/{book_id}/problems")["problems"]
        if p["code"].startswith(prefix or ("art_", "asset_", "map_"))
    ]


@pytest.fixture
def store(settings: Settings) -> Path:
    return settings.data_dir / "assets"


def test_upload_dedupes_and_serves_files(api: Api, series: Json, store: Path) -> None:
    a = upload(api, series["id"], png(1200, 900), "dragon.png")
    assert (a["width_px"], a["height_px"], a["mime"]) == (1200, 900, "image/png")
    assert (store / f"{a['sha256']}.png").is_file()
    same = upload(api, series["id"], png(1200, 900), "copy.png", expect=200)
    assert (same["id"], same["created"]) == (a["id"], False)

    res = api.c.get(a["url"])
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    thumb = api.c.get(a["thumb_url"])
    assert thumb.headers["content-type"] == "image/webp"
    with Image.open(io.BytesIO(thumb.content)) as im:
        assert max(im.size) <= 480

    upload(api, series["id"], b"not an image", expect=422)
    gif = io.BytesIO()
    Image.new("RGB", (4, 4)).save(gif, "GIF")
    upload(api, series["id"], gif.getvalue(), expect=422)

    edited = api.patch(
        f"/assets/{a['id']}", {"alt_text": "A red dragon", "tags": [" beast ", "beast", "red"]}
    )
    assert edited["tags"] == ["beast", "red"]
    assert [x["id"] for x in api.get(f"/series/{series['id']}/assets")] == [a["id"]]


def test_placement_dpi_follows_print_size(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    node = graph()["nodes"][0]
    a = upload(api, series["id"], png(1200, 900))
    api.patch(f"/assets/{a['id']}", {"alt_text": "Red"})
    pl = api.post(
        "/placements",
        {"target_type": "node", "target_id": node["id"], "asset_id": a["id"]},
    )
    assert (pl["role"], pl["status"], pl["layout"]["size"]) == ("illustration", "final", "half")
    # Half of a 117.4 mm text block: 1200 px over 58.7 mm.
    assert pl["print_size"]["width_mm"] == pytest.approx(58.7)
    assert pl["print_size"]["status"] == "good"
    assert problems(api, book["id"], "art_low_dpi") == []

    wide = api.patch(f"/placements/{pl['id']}", {"layout": {**pl["layout"], "size": "full_width"}})
    assert wide["print_size"]["status"] == "low"  # ~260 dpi
    (p,) = problems(api, book["id"], "art_low_dpi")
    assert (p["severity"], p["node_id"]) == ("warning", node["id"])

    bled = api.patch(
        f"/placements/{pl['id']}", {"layout": {**pl["layout"], "size": "full_page", "bleed": True}}
    )
    assert bled["print_size"]["status"] == "poor"
    assert problems(api, book["id"], "art_bleed")[0]["severity"] == "error"

    # A bigger trim lowers DPI further; the page setup drives every size.
    api.put(f"/books/{book['id']}/page-setup", {"trim_width_mm": 210, "trim_height_mm": 297})
    assert api.get(f"/placements?book_id={book['id']}")[0]["print_size"]["box_width_mm"] > 210
    api.put(
        f"/books/{book['id']}/page-setup",
        {"trim_width_mm": 100, "margin_inner_mm": 50, "margin_outer_mm": 40},
        expect=422,
    )

    # Canvas cards show the first illustration's thumbnail.
    assert graph()["nodes"][0]["art_thumb"] == a["thumb_url"]


def test_placeholders_roles_and_shot_list(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    g = graph()
    node, act = g["nodes"][0], g["acts"][0]
    hole = api.post(
        "/placements",
        {"target_type": "node", "target_id": node["id"], "brief": "A troll | under a bridge"},
    )
    assert (hole["status"], hole["asset"]) == ("needed", None)
    opener = api.post("/placements", {"target_type": "act", "target_id": act["id"]})
    assert (opener["role"], opener["layout"]["size"], opener["layout"]["page_side"]) == (
        "opener",
        "full_page",
        "recto",
    )
    cover = api.post(
        "/placements", {"target_type": "book", "target_id": book["id"], "role": "cover_front"}
    )
    assert cover["layout"]["bleed"] is True
    api.post(
        "/placements",
        {"target_type": "book", "target_id": book["id"], "role": "illustration"},
        expect=422,
    )
    assert {p["code"] for p in problems(api, book["id"], "art_placeholder")} == {"art_placeholder"}

    rows = api.get(f"/series/{series['id']}/shot-list?status=needed")
    assert len(rows) == 3
    troll = next(r for r in rows if r["brief"].startswith("A troll"))
    assert troll["needed_px"] == [693, 520]  # half width, 4:3 placeholder box at 300 dpi
    md = api.c.get(f"/api/series/{series['id']}/shot-list", params={"format": "md"})
    assert "A troll \\| under a bridge" in md.text
    csv = api.c.get(f"/api/series/{series['id']}/shot-list", params={"format": "csv"})
    assert csv.headers["content-type"].startswith("text/csv")
    assert "Front cover" in csv.text


def test_node_art_is_undoable(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    node = graph()["nodes"][0]
    a = upload(api, series["id"], png(600, 400))
    pl = api.post(
        "/placements", {"target_type": "node", "target_id": node["id"], "asset_id": a["id"]}
    )
    api.patch(f"/placements/{pl['id']}", {"caption": "The gate"})
    api.post(f"/books/{book['id']}/undo", expect=200)
    assert api.get(f"/placements?book_id={book['id']}")[0]["caption"] == ""
    api.post(f"/books/{book['id']}/undo", expect=200)
    assert api.get(f"/placements?book_id={book['id']}") == []
    api.post(f"/books/{book['id']}/redo", expect=200)
    (back,) = api.get(f"/placements?book_id={book['id']}")
    assert (back["id"], back["asset_id"]) == (pl["id"], a["id"])
    assert [u["id"] for u in api.get(f"/assets/{a['id']}/where-used")] == [pl["id"]]


def test_delete_guard_and_checkpoint_safe_gc(
    api: Api, series: Json, book: Json, graph: Callable[[], Json], store: Path
) -> None:
    node = graph()["nodes"][0]
    a = upload(api, series["id"], png(800, 600))
    file = store / f"{a['sha256']}.png"
    pl = api.post(
        "/placements", {"target_type": "node", "target_id": node["id"], "asset_id": a["id"]}
    )
    (use,) = api.get(f"/assets/{a['id']}/where-used")
    assert use["label"] == f"Illustration: {node['title']}"
    api.delete(f"/assets/{a['id']}", expect=409)

    cp = api.post("/checkpoints", {"name": "with art"})
    api.delete(f"/assets/{a['id']}?force=true")
    assert api.get(f"/placements?book_id={book['id']}")[0]["asset_id"] is None
    assert api.get(f"/placements?book_id={book['id']}")[0]["id"] == pl["id"]
    assert file.is_file()  # the checkpoint still names it

    api.delete(f"/checkpoints/{cp['id']}")
    # Freshly written files are kept for a grace period (an upload may be reusing them).
    assert api.post("/assets/gc", expect=200)["removed"] == 0
    old = time.time() - 3600
    for f in (file, store / "thumbs" / f"{a['sha256']}.webp"):
        os.utime(f, (old, old))
    assert api.post("/assets/gc", expect=200)["removed"] == 1
    assert not file.exists()


def test_unused_assets_and_missing_alt_text(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    a = upload(api, series["id"], png(10, 10))
    assert [p["code"] for p in problems(api, book["id"])] == ["asset_unused"]
    node = graph()["nodes"][0]
    api.post("/placements", {"target_type": "node", "target_id": node["id"], "asset_id": a["id"]})
    codes = {p["code"] for p in problems(api, book["id"])}
    assert "asset_unused" not in codes
    assert "art_alt_text" in codes


def test_maps_markers_and_the_player(
    api: Api,
    series: Json,
    playable: Json,
) -> None:
    a = upload(api, series["id"], png(1000, 700))
    m = api.post(
        f"/series/{series['id']}/maps", {"title": "The Valley", "book_id": playable["book_id"]}
    )
    assert m["key"] == "the_valley"
    markers = [
        {"id": "m1", "x": 0.2, "y": 0.3, "label": "Gate", "node_id": playable["start"]},
        {"id": "m2", "x": 0.7, "y": 0.6, "label": "Hoard", "visible_if": "flag(found_map)"},
    ]
    api.patch(f"/maps/{m['id']}", {"asset_id": a["id"], "markers": markers})
    api.patch(f"/maps/{m['id']}", {"markers": [{**markers[1], "visible_if": "flag("}]}, expect=422)
    api.patch(
        f"/maps/{m['id']}", {"markers": [markers[0], {**markers[0], "label": "dup"}]}, expect=422
    )

    url = f"/books/{playable['book_id']}/play"
    view = api.post(url, {"tier": "basic", "seed": 1}, expect=200)
    (vm,) = view["maps"]
    assert [(x["label"], x["here"]) for x in vm["markers"]] == [("Gate", True)]
    shown = api.post(
        url,
        {"tier": "basic", "seed": 1, "inputs": [{"kind": "set", "flags": {"found_map": True}}]},
        expect=200,
    )
    assert [x["label"] for x in shown["maps"][0]["markers"]] == ["Gate", "Hoard"]

    # Deleting the linked section breaks the marker (a warning, not data loss).
    tre = api.post(
        f"/books/{playable['book_id']}/nodes",
        {
            "act_id": api.get(f"/books/{playable['book_id']}/graph")["acts"][0]["id"],
            "title": "Ruins",
        },
    )
    api.patch(f"/maps/{m['id']}", {"markers": [{**markers[0], "node_id": tre["id"]}]})
    api.delete(f"/nodes/{tre['id']}")
    (p,) = problems(api, playable["book_id"], "map_marker_broken")
    assert p["severity"] == "warning"


def test_player_shows_digital_art_for_its_variant(
    api: Api,
    series: Json,
    playable: Json,
) -> None:
    a = upload(api, series["id"], png(300, 200))
    api.patch(f"/assets/{a['id']}", {"alt_text": "An orc", "caption": "The orc"})
    start = playable["start"]
    api.post(
        "/placements",
        {
            "target_type": "node",
            "target_id": start,
            "asset_id": a["id"],
            "digital": {"display": "full_width"},
        },
    )
    b = upload(api, series["id"], png(301, 200))
    api.post(
        "/placements",
        {"target_type": "node", "target_id": start, "asset_id": b["id"], "media": "print"},
    )
    view = api.post(f"/books/{playable['book_id']}/play", {"tier": "basic", "seed": 1}, expect=200)
    assert [(x["alt"], x["caption"], x["display"]) for x in view["art"]] == [
        ("An orc", "The orc", "full_width")
    ]


def test_appendices_render_tier_and_spoiler_aware(
    api: Api,
    series: Json,
    playable: Json,
) -> None:
    bid = playable["book_id"]
    orc = next(e for e in api.get(f"/series/{series['id']}/enemies") if e["key"] == "orc")
    face = upload(api, series["id"], png(200, 200))
    api.patch(f"/assets/{face['id']}", {"alt_text": "Orc face"})
    api.post(
        "/placements", {"target_type": "enemy", "target_id": orc["id"], "asset_id": face["id"]}
    )
    beast = api.post(f"/books/{bid}/appendices", {"kind": "bestiary", "options": {"tier": "basic"}})
    assert beast["title"] == "Bestiary"
    html = api.get(f"/appendices/{beast['id']}/render")
    assert "Orc" in html["html"]
    assert "SKILL" in html["html"] or "Skill" in html["html"]
    assert "6" in html["html"]  # SKILL 5 + level 1
    assert 'alt="Orc face"' in html["html"]
    assert html["document"].startswith("<!doctype html>")

    blank = api.patch(
        f"/appendices/{beast['id']}", {"options": {"tier": "basic", "blank_entries": True}}
    )
    assert blank["options"]["blank_entries"] is True
    assert 'class="box"' in api.get(f"/appendices/{beast['id']}/render")["html"]

    note = api.post(
        f"/books/{bid}/appendices",
        {
            "kind": "custom",
            "title": "Author's note",
            "options": {"body": "# Hi\n\n**Bold** <script>x</script> [[nobody]]"},
        },
    )
    out = api.get(f"/appendices/{note['id']}/render")["html"]
    assert "<strong>Bold</strong>" in out
    assert "<script>" not in out
    assert "&lt;script&gt;" in out

    sheet = api.post(f"/books/{bid}/appendices", {"kind": "sheet"})
    assert "Inventory" in api.get(f"/appendices/{sheet['id']}/render")["html"]
    rules = api.post(f"/books/{bid}/appendices", {"kind": "rules", "options": {"tier": "basic"}})
    assert "Combat" in api.get(f"/appendices/{rules['id']}/render")["html"]
    items = api.post(f"/books/{bid}/appendices", {"kind": "items"})
    for kind in ("personae", "glossary", "maps"):
        made = api.post(f"/books/{bid}/appendices", {"kind": kind})
        assert api.get(f"/appendices/{made['id']}/render")["html"]

    ids = [a["id"] for a in api.get(f"/books/{bid}/appendices")]
    flipped = api.post(f"/books/{bid}/appendices/reorder", {"ids": list(reversed(ids))}, expect=200)
    assert [a["id"] for a in flipped] == list(reversed(ids))
    api.patch(f"/appendices/{items['id']}", {"enabled": False})

    # The codex unlocks bestiary entries as they're met; the sheet and disabled ones stay out.
    codex = api.post(f"/books/{bid}/codex", {"tier": "basic"}, expect=200)
    titles = [c["title"] for c in codex]
    assert "Adventure Sheet" not in titles
    assert "Items" not in titles
    bestiary = next(c for c in codex if c["title"] == "Bestiary")
    assert "0 of 1 creatures met" in bestiary["document"]
    met = api.post(f"/books/{bid}/codex", {"tier": "basic", "enemies": ["orc"]}, expect=200)
    assert "1 of 1 creatures met" in next(c for c in met if c["title"] == "Bestiary")["document"]

    view = api.post(f"/books/{bid}/play", {"tier": "basic", "seed": 1}, expect=200)
    assert view["codex"]["available"] is True


def test_export_round_trip_keeps_art(
    api: Api,
    client: TestClient,
    series: Json,
    book: Json,
    graph: Callable[[], Json],
    store: Path,
) -> None:
    g = graph()
    node, act = g["nodes"][0], g["acts"][0]
    a = upload(api, series["id"], png(640, 480))
    api.patch(f"/assets/{a['id']}", {"alt_text": "Hall", "credit": "J. Artist"})
    api.post("/placements", {"target_type": "node", "target_id": node["id"], "asset_id": a["id"]})
    api.post("/placements", {"target_type": "act", "target_id": act["id"], "brief": "Storm"})
    m = api.post(f"/series/{series['id']}/maps", {"title": "World", "asset_id": a["id"]})
    api.patch(f"/maps/{m['id']}", {"markers": [{"id": "x", "x": 0.5, "y": 0.5, "label": "Here"}]})
    api.post(f"/books/{book['id']}/appendices", {"kind": "glossary"})
    api.put(f"/books/{book['id']}/page-setup", {"trim_width_mm": 140})

    res = client.get(f"/api/series/{series['id']}/export.zip")
    files, blobs = tree.from_zip_all(res.content)
    assert f"assets/{a['sha256']}.png" in blobs
    assert "credit: J. Artist" in files["assets.yaml"]
    assert "maps/world.yaml" in files

    # Wipe the stored file: the import must bring it back from the zip.
    (store / f"{a['sha256']}.png").unlink()
    back = client.post(
        "/api/import",
        content=res.content,
        params={"replace": True},
        headers={"Content-Type": "application/zip"},
    )
    assert back.status_code == 201, back.text
    assert (store / f"{a['sha256']}.png").is_file()
    placed = api.get(f"/placements?book_id={book['id']}")
    assert {(p["target_type"], p["asset_id"]) for p in placed} == {
        ("node", a["id"]),
        ("act", None),
    }
    assert api.get(f"/series/{series['id']}/maps")[0]["markers"][0]["label"] == "Here"
    assert api.get(f"/books/{book['id']}/appendices")[0]["kind"] == "glossary"
    assert api.get(f"/books/{book['id']}/page-setup")["trim_width_mm"] == 140
    again = tree.from_zip_all(client.get(f"/api/series/{series['id']}/export.zip").content)
    assert again[0] == files  # deterministic


# ── review regressions ────────────────────────────────────────────────────


def _zip_with_assets(
    client: TestClient, series_id: str, entry: dict[str, Any], blob: bytes | None
) -> bytes:
    files, blobs = tree.from_zip_all(client.get(f"/api/series/{series_id}/export.zip").content)
    files["assets.yaml"] = yaml.safe_dump({"assets": [entry]})
    if blob is not None:
        blobs[f"assets/{entry['sha256']}.{entry['ext']}"] = blob
    return tree.to_zip(files, blobs)


def _import(client: TestClient, data: bytes) -> Any:
    return client.post(
        "/api/import",
        content=data,
        params={"replace": True},
        headers={"Content-Type": "application/zip"},
    )


def test_import_trusts_only_the_image(
    client: TestClient, api: Api, series: Json, store: Path, settings: Settings
) -> None:
    secret = settings.data_dir.parent / "xx.png"
    secret.write_bytes(png(5, 5))
    evil = {"id": "a1", "sha256": "./" * 28 + "../../xx", "ext": "png", "mime": "text/html"}
    assert _import(client, _zip_with_assets(client, series["id"], evil, None)).status_code == 422

    # A real image whose YAML claims to be HTML is stored and served as what it is.
    data = png(30, 20)
    sha = hashlib.sha256(data).hexdigest()
    entry = {"id": "a2", "sha256": sha, "ext": "png", "mime": "text/html", "width_px": 9999}
    assert _import(client, _zip_with_assets(client, series["id"], entry, data)).status_code == 201
    (a,) = api.get(f"/series/{series['id']}/assets")
    assert (a["mime"], a["width_px"], a["height_px"]) == ("image/png", 30, 20)
    res = client.get(a["url"])
    assert res.headers["content-type"] == "image/png"
    assert res.headers["x-content-type-options"] == "nosniff"

    # Not an image (with a matching hash): refused, and nothing left in the store.
    junk = b"<script>alert(1)</script>"
    jsha = hashlib.sha256(junk).hexdigest()
    bad = {"id": "a3", "sha256": jsha, "ext": "png"}
    assert _import(client, _zip_with_assets(client, series["id"], bad, junk)).status_code == 422
    assert not (store / f"{jsha}.png").exists()

    # Listed twice: refused, not a 500.
    files, blobs = tree.from_zip_all(client.get(f"/api/series/{series['id']}/export.zip").content)
    rows = yaml.safe_load(files["assets.yaml"])["assets"]
    files["assets.yaml"] = yaml.safe_dump({"assets": [*rows, {**rows[0], "id": "dup"}]})
    assert _import(client, tree.to_zip(files, blobs)).status_code == 422

    # An entry with no file anywhere is skipped; its placements import as placeholders.
    ghost = {"id": "a4", "sha256": "ab" * 32, "ext": "png"}
    assert _import(client, _zip_with_assets(client, series["id"], ghost, None)).status_code == 201
    assert api.get(f"/series/{series['id']}/assets") == []


def test_uploads_reject_bombs_and_truncated_files(api: Api, series: Json, store: Path) -> None:
    big = io.BytesIO()
    Image.new("1", (17_000, 17_000)).save(big, "PNG")  # 289 Mpx, tiny on disk
    upload(api, series["id"], big.getvalue(), expect=422)
    jpg = io.BytesIO()
    Image.new("RGB", (400, 300), (10, 200, 10)).save(jpg, "JPEG")
    upload(api, series["id"], jpg.getvalue()[:-400], expect=422)
    assert not any(store.glob("*.jpg"))


def test_exif_orientation_sets_the_size(api: Api, series: Json) -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90°: a 400x200 sensor image displays 200x400
    out = io.BytesIO()
    Image.new("RGB", (400, 200)).save(out, "JPEG", exif=exif.tobytes())
    a = upload(api, series["id"], out.getvalue(), "photo.jpg")
    assert (a["width_px"], a["height_px"]) == (200, 400)
    with Image.open(io.BytesIO(api.c.get(a["thumb_url"]).content)) as im:
        assert im.size[0] < im.size[1]


def test_gc_keeps_everything_when_a_checkpoint_is_unreadable(
    api: Api, series: Json, store: Path, settings: Settings
) -> None:
    a = upload(api, series["id"], png(50, 50))
    api.delete(f"/assets/{a['id']}")
    file = store / f"{a['sha256']}.png"
    old = time.time() - 3600
    os.utime(file, (old, old))
    folder = settings.data_dir / "checkpoints"
    folder.mkdir(exist_ok=True)
    (folder / "20260101T000000000000__broken.db").write_bytes(b"not a database" * 100)
    api.post("/assets/gc", expect=409)
    assert file.is_file()


def test_deleting_a_variant_deletes_its_art(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    node = graph()["nodes"][0]
    v = api.post(f"/nodes/{node['id']}/variants", {"label": "Has rope", "condition": "has(rope)"})
    a = upload(api, series["id"], png(40, 40))
    pl = api.post(
        "/placements",
        {
            "target_type": "node",
            "target_id": node["id"],
            "asset_id": a["id"],
            "variant_id": v["id"],
        },
    )
    assert pl["variant_id"] == v["id"]
    api.delete(f"/variants/{v['id']}")
    assert api.get(f"/placements?book_id={book['id']}") == []
    assert api.get(f"/assets/{a['id']}/where-used") == []


def test_codex_uses_the_readers_tier_and_hides_conditional_markers(
    api: Api,
    series: Json,
    playable: Json,
) -> None:
    bid = playable["book_id"]
    a = upload(api, series["id"], png(100, 100))
    m = api.post(f"/series/{series['id']}/maps", {"title": "Vale", "asset_id": a["id"]})
    api.patch(
        f"/maps/{m['id']}",
        {
            "markers": [
                {"id": "a", "x": 0.1, "y": 0.1, "label": "Town"},
                {"id": "b", "x": 0.5, "y": 0.5, "label": "Secret hoard", "visible_if": "flag(map)"},
            ]
        },
    )
    maps = api.post(f"/books/{bid}/appendices", {"kind": "maps"})
    assert "Secret hoard" in api.get(f"/appendices/{maps['id']}/render")["html"]  # author view
    rules = api.post(f"/books/{bid}/appendices", {"kind": "rules"})
    assert "Advanced" in api.get(f"/appendices/{rules['id']}/render")["html"]
    codex = {
        c["title"]: c["document"]
        for c in api.post(f"/books/{bid}/codex", {"tier": "basic"}, expect=200)
    }
    assert "Town" in codex["Maps"]
    assert "Secret hoard" not in codex["Maps"]
    assert "Basic rules" in codex["Rules Reference"]


def test_tiers_are_validated_and_csv_cells_escaped(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    node = graph()["nodes"][0]
    api.post(
        "/placements", {"target_type": "node", "target_id": node["id"], "tier": "nope"}, expect=422
    )
    api.post(
        f"/books/{book['id']}/appendices",
        {"kind": "rules", "options": {"tier": "nope"}},
        expect=422,
    )
    api.post(
        "/placements",
        {"target_type": "node", "target_id": node["id"], "brief": '=HYPERLINK("x")'},
    )
    csv = api.c.get(f"/api/series/{series['id']}/shot-list", params={"format": "csv"}).text
    assert "'=HYPERLINK" in csv


def test_series_map_markers_to_deleted_sections_are_reported(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    act = graph()["acts"][0]
    n = api.post(f"/books/{book['id']}/nodes", {"act_id": act["id"], "title": "Ruins"})
    m = api.post(f"/series/{series['id']}/maps", {"title": "World"})
    api.patch(
        f"/maps/{m['id']}", {"markers": [{"id": "r", "x": 0.3, "y": 0.3, "node_id": n["id"]}]}
    )
    api.delete(f"/nodes/{n['id']}")
    assert [p["code"] for p in problems(api, book["id"], "map_marker_broken")] == [
        "map_marker_broken"
    ]
