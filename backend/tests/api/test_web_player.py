"""Phase 12 API: the standalone web player export."""

from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import pytest

from gamebook.config import Settings

from .conftest import Api, Json
from .test_art import png, upload
from .test_playtest import playable

__all__ = ["playable"]


@pytest.fixture
def player_dist(tmp_path: Path) -> Path:
    """A stand-in for frontend/dist-player (the real one is built by `make build`)."""
    d = tmp_path / "dist-player"
    (d / "assets").mkdir(parents=True)
    (d / "player.html").write_text(
        "<html><head><title><!-- GAMEBOOK_TITLE --></title>"
        '<script src="./book.js"></script>'
        '<script type="module" crossorigin src="./assets/player.js"></script>'
        '<link rel="stylesheet" crossorigin href="./assets/style.css"></head></html>'
    )
    (d / "assets" / "player.js").write_text("console.log('player')")
    (d / "assets" / "style.css").write_text("body{}")
    return d


@pytest.fixture
def settings(tmp_path: Path, player_dist: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        cors_origins=["http://testserver"],
        sim_processes=1,
        player_dist=player_dist,
    )


def wait_job(api: Api, job_id: str) -> Json:
    end = time.monotonic() + 60
    while time.monotonic() < end:
        job: Json = api.get(f"/jobs/{job_id}")
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError("job still running")


def _export(api: Api, book_id: str) -> zipfile.ZipFile:
    job = api.post(f"/books/{book_id}/print/exports", {"format": "web"})
    done = wait_job(api, job["id"])
    assert done["status"] == "done", done
    res = api.c.get(f"/api/print/exports/{job['id']}")
    assert res.headers["content-type"] == "application/zip"
    assert done["result"]["file"].endswith("-web.zip")
    return zipfile.ZipFile(io.BytesIO(res.content))


def test_web_player_bundles_the_book(
    api: Api,
    series: Json,
    playable: Json,
) -> None:
    bid = playable["book_id"]
    graph = api.get(f"/books/{bid}/graph")
    start = next(n for n in graph["nodes"] if n["id"] == playable["start"])
    api.post(
        f"/variants/{start['variants'][0]['id']}/prose",
        {"text": "An orc blocks the bridge.", "approve": True},
    )
    # A second, unwritten version of the section: readers who get it see the notes.
    api.patch(f"/nodes/{playable['start']}", {"beat_notes": "The orc snarls."})
    api.post(f"/nodes/{playable['start']}/variants", {"label": "Later", "condition": "flag(x)"})
    a = upload(api, series["id"], png(2400, 1600))
    api.patch(f"/assets/{a['id']}", {"alt_text": "An orc"})
    api.post(
        "/placements",
        {
            "target_type": "node",
            "target_id": playable["start"],
            "asset_id": a["id"],
            "media": "print",
        },
    )
    b = upload(api, series["id"], png(2401, 1600))
    api.post(
        "/placements", {"target_type": "node", "target_id": playable["start"], "asset_id": b["id"]}
    )
    api.post(f"/books/{bid}/appendices", {"kind": "bestiary"})
    api.post(f"/books/{bid}/appendices", {"kind": "sheet"})
    m = api.post(f"/series/{series['id']}/maps", {"title": "Vale", "asset_id": b["id"]})
    api.patch(
        f"/maps/{m['id']}",
        {"markers": [{"id": "x", "x": 0.5, "y": 0.5, "label": "Hoard", "visible_if": "flag(map)"}]},
    )

    with _export(api, bid) as z:
        names = z.namelist()
        index = z.read("index.html").decode()
        assert '<script defer src="./assets/player.js">' in index  # runs from file:// too
        assert "crossorigin" not in index
        assert "<!-- GAMEBOOK_TITLE -->" not in index  # the book's title replaced it
        assert {"book.js", "sw.js", "manifest.webmanifest", "icon.svg", "assets/player.js"} <= set(
            names
        )
        js = z.read("book.js").decode()
        assert js.startswith("window.GAMEBOOK = ")
        data = json.loads(js[len("window.GAMEBOOK = ") :].rstrip().rstrip(";"))
        assert (data["format"], data["version"]) == ("gamebook-player", 1)
        assert data["bundle"]["format"] == "gamebook-bundle"
        assert [t["key"] for t in data["tiers"]] == ["basic", "medium", "advanced"]
        assert "An orc blocks the bridge." in data["text"].values()
        assert data["notes"][playable["start"]] == "The orc snarls."
        # Only digital art; scaled for screens.
        (art,) = data["art"][playable["start"]]
        assert art["file"].startswith("images/")
        from PIL import Image

        with Image.open(io.BytesIO(z.read(art["file"]))) as im:
            assert max(im.size) <= 1600
        assert data["maps"][0]["markers"][0]["visible_if"] == "flag(map)"
        # The codex: one set of pages per tier; no adventure sheet; entries keyed to unlock.
        basic = data["codex"]["basic"]
        assert [p["kind"] for p in basic] == ["bestiary"]
        assert 'data-enemy="orc"' in basic[0]["html"]
        assert basic[0]["html"].startswith("<!doctype html>")
        sw = z.read("sw.js").decode()
        assert '"book.js"' in sw
        # Per-book caches (other books on the site keep theirs); one file at a time.
        assert f'const PREFIX = "gamebook-{bid}-"' in sw
        assert "k.startsWith(PREFIX)" in sw
        assert "allSettled" in sw
        assert json.loads(z.read("manifest.webmanifest"))["display"] == "standalone"


def test_web_player_needs_a_build(
    api: Api, playable: Json, settings: Settings, player_dist: Path
) -> None:
    (player_dist / "player.html").unlink()
    job = api.post(f"/books/{playable['book_id']}/print/exports", {"format": "web"})
    done = wait_job(api, job["id"])
    assert done["status"] == "failed"
    assert "make build" in done["error"]
