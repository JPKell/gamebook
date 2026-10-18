"""Phase 5 API: the in-app player, bot batches, replays, coverage and jobs."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gamebook.config import Settings

from .conftest import Api, Json


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # In-process bot runs keep the API tests fast; one test covers the process pool.
    return Settings(data_dir=tmp_path / "data", cors_origins=["http://testserver"], sim_processes=1)


@pytest.fixture
def playable(api: Api, series: Json, book: Json, graph: Callable[[], Json]) -> Json:
    """Start → fight an orc or test your luck → treasure (victory) or dead (death)."""
    start = graph()["nodes"][0]
    act = start["act_id"]
    treasure = api.post(f"/books/{book['id']}/nodes", {"act_id": act, "title": "Treasure"})
    dead = api.post(f"/books/{book['id']}/nodes", {"act_id": act, "title": "Dead"})
    api.patch(f"/nodes/{treasure['id']}", {"ending_kind": "victory"})
    api.patch(f"/nodes/{dead['id']}", {"ending_kind": "death"})
    api.post(f"/series/{series['id']}/items", {"name": "Rope", "stackable": True})
    orc = api.post(
        f"/series/{series['id']}/enemies",
        {"name": "Orc", "stat_formulas": {"SKILL": "5 + level", "STAMINA": "4 + level * 2"}},
    )
    enc = api.post(
        f"/nodes/{start['id']}/encounters",
        {"label": "Orc", "enemies": [{"enemy_id": orc["id"], "level": 1}]},
    )
    fight = api.post(f"/nodes/{start['id']}/choices", {"label": "Fight", "kind": "combat"})
    api.patch(
        f"/choices/{fight['id']}",
        {
            "encounter_id": enc["id"],
            "outcomes": [
                {"key": "win", "target_node_id": treasure["id"]},
                {"key": "lose", "target_node_id": dead["id"]},
            ],
        },
    )
    luck = api.post(
        f"/nodes/{start['id']}/choices", {"label": "Luck", "kind": "test", "test": "luck"}
    )
    api.patch(
        f"/choices/{luck['id']}",
        {
            "outcomes": [
                {"key": "success", "target_node_id": treasure["id"]},
                {"key": "failure", "target_node_id": dead["id"]},
            ]
        },
    )
    return {
        "book_id": book["id"],
        "start": start["id"],
        "treasure": treasure["id"],
        "dead": dead["id"],
        "fight": fight["id"],
        "luck": luck["id"],
    }


def wait_job(api: Api, job_id: str, timeout: float = 60) -> Json:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job: Json = api.get(f"/jobs/{job_id}")
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} still running")


# ── player ───────────────────────────────────────────────────────────────


def test_play_start_and_step(api: Api, playable: Json) -> None:
    url = f"/books/{playable['book_id']}/play"
    first = api.post(url, {"tier": "basic", "seed": 3}, expect=200)
    assert first["node"]["id"] == playable["start"]
    assert first["applied"] == 0
    assert first["error"] is None
    assert {s["key"] for s in first["stats"]} >= {"SKILL", "STAMINA", "LUCK"}
    assert any(e["type"] == "character_created" and e["text"] for e in first["events"])
    labels = [a["label"] for a in first["actions"]]
    assert "Fight" in labels
    assert "Luck" in labels

    inputs: list[dict[str, Any]] = [
        {"kind": "action", "type": "choose", "target": playable["luck"]}
    ]
    after = api.post(url, {"tier": "basic", "seed": 3, "inputs": inputs}, expect=200)
    assert after["applied"] == 1
    assert after["ended"] in ("victory", "death")
    assert any(e["type"] == "test" and e["turn"] == 0 for e in after["events"])
    # Deterministic: same inputs, same result.
    again = api.post(url, {"tier": "basic", "seed": 3, "inputs": inputs}, expect=200)
    assert again["events"] == after["events"]


def test_play_fight_to_the_end(api: Api, playable: Json) -> None:
    url = f"/books/{playable['book_id']}/play"
    inputs: list[dict[str, Any]] = [
        {"kind": "action", "type": "choose", "target": playable["fight"]}
    ]
    out = api.post(url, {"tier": "basic", "seed": 5, "inputs": inputs}, expect=200)
    assert out["combat"]["enemies"][0]["name"] == "Orc"
    for _ in range(100):
        if not out["combat"]:
            break
        inputs.append({"kind": "action", "type": "attack"})
        out = api.post(url, {"tier": "basic", "seed": 5, "inputs": inputs}, expect=200)
    assert out["ended"] in ("victory", "death")
    assert any(e["type"] == "combat_round" and "Round 1" in e["text"] for e in out["events"])


def test_play_debug_inputs(api: Api, playable: Json) -> None:
    url = f"/books/{playable['book_id']}/play"
    inputs: list[dict[str, Any]] = [
        {"kind": "set", "stats": {"LUCK": 12}, "items": {"rope": 2}, "flags": {"SEEN": True}},
        {"kind": "force", "total": 2},
        {"kind": "action", "type": "choose", "target": playable["luck"]},
    ]
    out = api.post(url, {"tier": "basic", "inputs": inputs}, expect=200)
    assert out["applied"] == 3, out["error"]
    assert out["node"]["id"] == playable["treasure"]  # forced 2 ≤ LUCK 12
    assert out["flags"] == ["SEEN"]
    assert {i["key"]: i["count"] for i in out["items"]} == {"rope": 2}
    jumped = api.post(
        url,
        {"tier": "basic", "inputs": [{"kind": "jump", "node_id": playable["dead"]}]},
        expect=200,
    )
    assert jumped["ended"] == "death"


def test_play_stops_where_the_book_changed(api: Api, playable: Json) -> None:
    url = f"/books/{playable['book_id']}/play"
    inputs: list[dict[str, Any]] = [
        {"kind": "action", "type": "choose", "target": "gone"},
        {"kind": "action", "type": "attack"},
    ]
    out = api.post(url, {"tier": "basic", "inputs": inputs}, expect=200)
    assert out["applied"] == 0
    assert "Step 1 no longer applies" in out["error"]
    assert out["node"]["id"] == playable["start"]


def test_play_validation(api: Api, playable: Json, series: Json) -> None:
    url = f"/books/{playable['book_id']}/play"
    api.post(url, {"tier": "nope"}, expect=422)
    api.post(url, {"tier": "basic", "inputs": [{"kind": "warp"}]}, expect=422)
    api.post("/books/missing/play", {"tier": "basic"}, expect=404)


# ── batches ──────────────────────────────────────────────────────────────


def test_bots_listed(api: Api) -> None:
    names = [b["name"] for b in api.get("/playtest/bots")]
    assert names == ["random", "greedy", "cautious", "explorer", "completionist"]


def test_batch_runs_summarises_and_replays(api: Api, playable: Json) -> None:
    bid = playable["book_id"]
    batch = api.post(
        f"/books/{bid}/batches", {"tier": "basic", "runs": 300, "player": {"bot": "random"}}
    )
    assert batch["status"] in ("queued", "running", "done")
    job = wait_job(api, batch["job_id"])
    assert job["status"] == "done", job
    assert job["progress"] == job["total"] == 300

    detail = api.get(f"/batches/{batch['id']}")
    s = detail["summary"]
    assert detail["status"] == "done"
    assert not detail["stale"]
    assert s["runs"] == 300
    assert sum(s["outcomes"].values()) == 300
    assert set(s["outcomes"]) <= {"victory", "death"}
    assert 0 < s["win_rate"] < 1
    assert s["node_visits"][playable["start"]] == 300
    assert s["coverage"]["nodes_total"] == 3
    assert s["coverage"]["nodes_visited"] == 3
    assert "orc" in s["enemies"]
    assert detail["names"]["nodes"][playable["treasure"]] == "Treasure"

    listed = api.get(f"/books/{bid}/batches")
    assert listed[0]["id"] == batch["id"]
    assert listed[0]["win_rate"] == s["win_rate"]

    page = api.get(f"/batches/{batch['id']}/runs?outcome=death&limit=5")
    assert page["total"] == s["outcomes"]["death"]
    run = page["runs"][0]
    assert run["outcome"] == "death"

    full = api.get(f"/batches/{batch['id']}/runs/{run['index']}/replay")
    assert full["ended"] == "death"
    assert full["steps"] == run["steps"]
    first = api.get(f"/batches/{batch['id']}/runs/{run['index']}/replay?upto=0")
    assert first["steps"] == 0
    assert first["node"]["id"] == playable["start"]

    # Editing the book marks the batch stale; replays still use the batch's bundle.
    api.patch(f"/nodes/{playable['treasure']}", {"title": "Gold"})
    assert api.get(f"/batches/{batch['id']}")["stale"] is True
    again = api.get(f"/batches/{batch['id']}/runs/{run['index']}/replay")
    assert again["events"] == full["events"]

    api.delete(f"/batches/{batch['id']}")
    api.get(f"/batches/{batch['id']}", expect=404)


def test_batches_are_deterministic(api: Api, playable: Json) -> None:
    bid = playable["book_id"]
    body = {"tier": "basic", "runs": 50, "seed_base": 9, "player": {"bot": "cautious"}}
    a = api.post(f"/books/{bid}/batches", body)
    b = api.post(f"/books/{bid}/batches", body)
    wait_job(api, a["job_id"])
    wait_job(api, b["job_id"])
    sa = api.get(f"/batches/{a['id']}")["summary"]
    sb = api.get(f"/batches/{b['id']}")["summary"]
    assert sa == sb
    assert a["content_hash"] == b["content_hash"]


def test_batch_validation(api: Api, playable: Json) -> None:
    bid = playable["book_id"]
    api.post(f"/books/{bid}/batches", {"tier": "nope"}, expect=422)
    api.post(f"/books/{bid}/batches", {"tier": "basic", "runs": 0}, expect=422)
    api.post(f"/books/{bid}/batches", {"tier": "basic", "player": {"bot": "psychic"}}, expect=422)
    api.post(
        f"/books/{bid}/batches", {"tier": "basic", "runs": 20_000, "max_steps": 500}, expect=422
    )
    api.post(
        f"/books/{bid}/batches", {"tier": "basic", "seed_base": 2**31 - 5, "runs": 10}, expect=422
    )
    api.get("/batches/missing", expect=404)
    api.get("/jobs/missing", expect=404)


def test_cancel_a_batch(api: Api, playable: Json) -> None:
    bid = playable["book_id"]
    batch = api.post(f"/books/{bid}/batches", {"tier": "basic", "runs": 20_000, "max_steps": 100})
    api.post(f"/jobs/{batch['job_id']}/cancel", None, expect=200)
    job = wait_job(api, batch["job_id"])
    assert job["status"] == "cancelled"
    assert api.get(f"/batches/{batch['id']}")["status"] == "cancelled"
    api.post(f"/jobs/{batch['job_id']}/cancel", None, expect=409)


def test_job_events_stream(api: Api, client: TestClient, playable: Json) -> None:
    batch = api.post(f"/books/{playable['book_id']}/batches", {"tier": "basic", "runs": 100})
    with client.stream("GET", f"/api/jobs/{batch['job_id']}/events") as res:
        assert res.headers["content-type"].startswith("text/event-stream")
        lines = [ln for ln in res.iter_lines() if ln.startswith("data: ")]
    assert '"status": "done"' in lines[-1]


def test_coverage_walk(api: Api, playable: Json) -> None:
    job = api.post(f"/books/{playable['book_id']}/coverage", {"tier": "basic", "samples": 3})
    done = wait_job(api, job["id"])
    assert done["status"] == "done", done
    r = done["result"]
    assert set(r["reached"]) == {playable["start"], playable["treasure"], playable["dead"]}
    assert r["unreached"] == []
    assert set(r["endings"]) == {playable["treasure"], playable["dead"]}


def test_process_pool(tmp_path: Path) -> None:
    from gamebook.api import create_app

    settings = Settings(data_dir=tmp_path / "data", sim_processes=2)
    with TestClient(create_app(settings)) as c:
        api = Api(c)
        s = api.post("/series", {"title": "Pool"})
        b = api.post(f"/series/{s['id']}/books", {"title": "B"})
        start = api.get(f"/books/{b['id']}/graph")["nodes"][0]
        end = api.post(
            f"/books/{b['id']}/nodes",
            {"act_id": start["act_id"], "link_from": {"node_id": start["id"]}},
        )
        api.patch(f"/nodes/{end['id']}", {"ending_kind": "victory"})
        batch = api.post(f"/books/{b['id']}/batches", {"tier": "basic", "runs": 500})
        job = wait_job(api, batch["job_id"], timeout=120)
        assert job["status"] == "done", job
        assert api.get(f"/batches/{batch['id']}")["summary"]["win_rate"] == 1.0


def test_restart_fails_interrupted_jobs_and_batches(tmp_path: Path) -> None:
    from gamebook.api import create_app
    from gamebook.db.models import Job, PlaytestBatch
    from gamebook.db.session import Database

    settings = Settings(data_dir=tmp_path / "data", sim_processes=1)
    with TestClient(create_app(settings)) as c:
        api = Api(c)
        s = api.post("/series", {"title": "R"})
        b = api.post(f"/series/{s['id']}/books", {"title": "B"})
        batch = api.post(f"/books/{b['id']}/batches", {"tier": "basic", "runs": 5})
        wait_job(api, batch["job_id"])
    # Simulate a crash mid-run.
    db = Database(settings.database_url)
    with db.session() as session:
        session.get_one(Job, batch["job_id"]).status = "running"
        session.get_one(PlaytestBatch, batch["id"]).status = "running"
    db.dispose()
    with TestClient(create_app(settings)) as c:
        api = Api(c)
        assert api.get(f"/jobs/{batch['job_id']}")["status"] == "failed"
        assert api.get(f"/batches/{batch['id']}")["status"] == "failed"


def test_debug_set_rejects_unknown_keys(api: Api, playable: Json) -> None:
    url = f"/books/{playable['book_id']}/play"
    out = api.post(
        url, {"tier": "basic", "inputs": [{"kind": "set", "stats": {"MANA": 3}}]}, expect=200
    )
    assert out["applied"] == 0
    assert "Unknown stat or item: MANA" in out["error"]


def test_deleting_a_batch_removes_its_job(api: Api, playable: Json) -> None:
    batch = api.post(f"/books/{playable['book_id']}/batches", {"tier": "basic", "runs": 5})
    wait_job(api, batch["job_id"])
    api.delete(f"/batches/{batch['id']}")
    api.get(f"/jobs/{batch['job_id']}", expect=404)


def test_cancelled_batch_is_final_before_its_job(api: Api, playable: Json) -> None:
    """Review regression: the job turned terminal while its batch still said running."""
    batch = api.post(
        f"/books/{playable['book_id']}/batches", {"tier": "basic", "runs": 20_000, "max_steps": 100}
    )
    api.post(f"/jobs/{batch['job_id']}/cancel", None, expect=200)
    wait_job(api, batch["job_id"])
    assert api.get(f"/batches/{batch['id']}")["status"] == "cancelled"
