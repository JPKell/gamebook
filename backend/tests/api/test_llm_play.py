"""Phase 9 API: LLM players in playtest batches (offline model only)."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from gamebook.core.sim.reader import NO_TEXT
from gamebook.db.models import Job
from gamebook.llm import fake

from .conftest import Api, Json
from .test_playtest import playable, settings, wait_job

__all__ = ["playable", "settings"]


@pytest.fixture(autouse=True)
def clear_script() -> Iterator[None]:
    fake.SCRIPT.clear()
    yield
    fake.SCRIPT.clear()


@pytest.fixture
def provider(api: Api) -> Json:
    p: Json = api.post(
        "/llm/providers",
        {
            "name": "Offline",
            "kind": "fake",
            "max_concurrency": 2,
            "models": [{"id": "offline", "input_per_mtok": 1000, "output_per_mtok": 1000}],
        },
    )
    return p


def llm_batch(api: Api, book_id: str, provider: Json, **extra: object) -> Json:
    body: Json = {
        "tier": "basic",
        "runs": 3,
        "max_steps": 20,
        "player": {"kind": "llm", "provider_id": provider["id"], "model": "offline"},
        **extra,
    }
    b: Json = api.post(f"/books/{book_id}/batches", body, expect=201)
    return b


def test_llm_players_play_and_explain(api: Api, playable: Json, provider: Json) -> None:
    b = llm_batch(api, playable["book_id"], provider, label="LLM run")
    job = wait_job(api, b["job_id"])
    assert job["status"] == "done", job
    detail = api.get(f"/batches/{b['id']}")
    assert detail["status"] == "done"
    assert detail["summary"]["runs"] == 3
    assert detail["summary"]["outcomes"].get("error") is None
    assert detail["cost_usd"] > 0
    # The fake player attacks: every run fights the orc at the start.
    assert detail["summary"]["enemies"]["orc"]["fights"] == 3
    llm = detail["summary"]["llm"]
    # The book has no prose, so the player is confused at every step and says where.
    assert llm["confused_steps"] == llm["steps"] > 0
    assert llm["confusion"][0]["node_id"] == playable["start"]
    assert "no text" in llm["confusion"][0]["notes"][0]["text"]

    runs = api.get(f"/batches/{b['id']}/runs")["runs"]
    assert all(r["cost_usd"] > 0 and r["confused_steps"] == r["steps"] for r in runs)
    first = api.get(f"/batches/{b['id']}/runs/0/replay?upto=0")
    assert first["next_note"]["option"].lower().startswith("fight")
    assert first["next_note"]["reasoning"]
    end = api.get(f"/batches/{b['id']}/runs/0/replay")
    assert end["next_note"] is None
    assert end["ended"] in ("victory", "death", "defeated")

    calls = api.get("/llm/calls?role=player")
    assert calls["total"] >= sum(r["steps"] for r in runs)
    prompt = api.get(f"/llm/calls/{calls['calls'][0]['id']}")["messages"][1]["content"]
    assert NO_TEXT in prompt
    assert "YOUR ADVENTURE SHEET" in prompt
    assert "Treasure" not in prompt  # never a section title the reader can't see


def test_player_sees_prose_and_bad_choices_are_retried(
    api: Api,
    playable: Json,
    provider: Json,
) -> None:
    start = next(
        n
        for n in api.get(f"/books/{playable['book_id']}/graph")["nodes"]
        if n["id"] == playable["start"]
    )
    api.post(
        f"/variants/{start['variants'][0]['id']}/prose",
        {"text": "An orc blocks the road.", "approve": True},
    )
    ok = {"choice": 2, "reasoning": "Luck it is.", "memory": "Met an orc.", "confused": False}
    fake.SCRIPT["player"] += [
        json.dumps({**ok, "choice": 7}),  # out of range: asked again
        json.dumps(ok),
    ]
    b = llm_batch(api, playable["book_id"], provider, runs=1)
    assert wait_job(api, b["job_id"])["status"] == "done"
    note = api.get(f"/batches/{b['id']}/runs/0/replay?upto=0")["next_note"]
    assert (note["choice"], note["option"], note["confused"]) == (1, "Luck", False)
    first = api.get("/llm/calls?role=player")["calls"][-1]
    assert (
        "An orc blocks the road." in api.get(f"/llm/calls/{first['id']}")["messages"][1]["content"]
    )


def test_budget_stops_and_resume_finishes(api: Api, playable: Json, provider: Json) -> None:
    b = llm_batch(api, playable["book_id"], provider, runs=4, budget_usd=0.000001)
    job = wait_job(api, b["job_id"])
    assert job["status"] == "done"
    assert job["result"]["status"] == "stopped"
    detail = api.get(f"/batches/{b['id']}")
    assert detail["status"] == "stopped"
    assert detail["summary"]["llm"]["stopped_runs"] >= 1
    spent = detail["cost_usd"]
    api.post(f"/batches/{b['id']}/resume", {}, expect=422)  # still over budget

    resumed = api.post(f"/batches/{b['id']}/resume", {"budget_usd": 100}, expect=200)
    assert wait_job(api, resumed["job_id"])["status"] == "done"
    detail = api.get(f"/batches/{b['id']}")
    assert detail["status"] == "done"
    assert detail["summary"]["runs"] == 4
    assert detail["summary"]["llm"]["stopped_runs"] == 0
    assert detail["cost_usd"] > spent
    api.post(f"/batches/{b['id']}/resume", {}, expect=409)  # nothing left to play


def test_llm_batches_are_validated(api: Api, playable: Json, provider: Json) -> None:
    url = f"/books/{playable['book_id']}/batches"
    player = {"kind": "llm", "provider_id": provider["id"], "model": "offline"}
    api.post(url, {"tier": "basic", "runs": 500, "player": player}, expect=422)
    api.post(url, {"tier": "basic", "runs": 2, "max_steps": 1000, "player": player}, expect=422)
    api.post(
        url, {"tier": "basic", "runs": 2, "player": {**player, "provider_id": "nope"}}, expect=422
    )
    api.post(url, {"tier": "basic", "runs": 2, "player": {**player, "persona": "x"}}, expect=422)
    # Bots still work without a kind, and can't be resumed.
    bot = api.post(url, {"tier": "basic", "runs": 5, "player": {"bot": "random"}}, expect=201)
    wait_job(api, bot["job_id"])
    api.post(f"/batches/{bot['id']}/resume", {}, expect=409)


def _player_spend(api: Api) -> float:
    calls = api.get("/llm/calls?role=player&limit=500")["calls"]
    return round(sum(float(c["cost_usd"]) for c in calls), 6)


def test_a_bad_choice_then_bad_json_is_retried_and_paid_for(
    api: Api,
    playable: Json,
    provider: Json,
) -> None:
    ok = {"choice": 2, "reasoning": "Luck.", "memory": "", "confused": False}
    fake.SCRIPT["player"] += [
        json.dumps({**ok, "choice": 9}),  # out of range: re-asked
        "not json",  # the re-ask's reply isn't JSON: re-asked again
        json.dumps(ok),
    ]
    b = llm_batch(api, playable["book_id"], provider, runs=1)
    assert wait_job(api, b["job_id"])["status"] == "done"
    (run,) = api.get(f"/batches/{b['id']}/runs")["runs"]
    assert run["outcome"] != "error", run
    assert api.get(f"/batches/{b['id']}")["cost_usd"] == pytest.approx(_player_spend(api))


def test_resume_keeps_the_spend_of_replayed_runs(
    api: Api,
    playable: Json,
    provider: Json,
) -> None:
    b = llm_batch(api, playable["book_id"], provider, runs=4, budget_usd=0.000001)
    wait_job(api, b["job_id"])
    resumed = api.post(f"/batches/{b['id']}/resume", {"budget_usd": 100}, expect=200)
    wait_job(api, resumed["job_id"])
    # Every call is paid for, including those of the stopped runs that were replayed.
    assert api.get(f"/batches/{b['id']}")["cost_usd"] == pytest.approx(_player_spend(api))


def test_a_failing_model_stops_the_batch_and_resume_replays_its_runs(
    api: Api,
    playable: Json,
    provider: Json,
) -> None:
    bad = json.dumps({"choice": 99, "reasoning": "", "memory": ""})
    fake.SCRIPT["player"] += [bad] * 40
    b = llm_batch(api, playable["book_id"], provider, runs=6)
    job = wait_job(api, b["job_id"])
    assert job["status"] == "failed"
    assert "failed 3 times in a row" in job["error"]
    detail = api.get(f"/batches/{b['id']}")
    assert detail["status"] == "failed"
    assert detail["summary"]["llm"]["failed_runs"] >= 1
    assert detail["summary"]["errors"]["runs"] == 0  # not a content error

    fake.SCRIPT.clear()  # the provider is fixed
    resumed = api.post(f"/batches/{b['id']}/resume", {}, expect=200)
    assert wait_job(api, resumed["job_id"])["status"] == "done"
    detail = api.get(f"/batches/{b['id']}")
    assert detail["status"] == "done"
    assert detail["summary"]["runs"] == 6
    assert detail["summary"]["llm"]["failed_runs"] == 0


def test_deleting_a_resumed_batch_removes_all_its_jobs(
    api: Api,
    playable: Json,
    provider: Json,
) -> None:
    b = llm_batch(api, playable["book_id"], provider, runs=2, budget_usd=0.000001)
    wait_job(api, b["job_id"])
    resumed = api.post(f"/batches/{b['id']}/resume", {"budget_usd": 100}, expect=200)
    wait_job(api, resumed["job_id"])
    api.delete(f"/batches/{b['id']}")
    api.get(f"/jobs/{b['job_id']}", expect=404)
    api.get(f"/jobs/{resumed['job_id']}", expect=404)


def test_llm_player_model_must_be_listed(api: Api, playable: Json, provider: Json) -> None:
    player = {"kind": "llm", "provider_id": provider["id"], "model": "missing"}
    api.post(
        f"/books/{playable['book_id']}/batches",
        {"tier": "basic", "runs": 1, "player": player},
        expect=422,
    )


def test_llm_batches_have_their_own_job_lane(api: Api, client: TestClient) -> None:
    runner = client.app.state.jobs  # type: ignore[attr-defined]
    gate = threading.Event()
    with runner.db.session() as s:
        slow, quick = Job(kind="t", label="slow"), Job(kind="t", label="quick")
        s.add_all([slow, quick])
        s.flush()
        slow_id, quick_id = slow.id, quick.id
    runner.submit(slow_id, lambda _ctx: gate.wait(10) and {}, lane="llm")
    runner.submit(quick_id, lambda _ctx: {"ok": True})
    try:
        assert wait_job(api, quick_id, timeout=5)["status"] == "done"
    finally:
        gate.set()
    assert wait_job(api, slow_id)["status"] == "done"
