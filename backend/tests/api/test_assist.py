"""Phase 8 API: consistency checker, beat/branch suggester and lore extractor (offline model)."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import pytest

from gamebook.llm import fake

from .conftest import Api, Json


@pytest.fixture(autouse=True)
def clear_script() -> Iterator[None]:
    fake.SCRIPT.clear()
    yield
    fake.SCRIPT.clear()


def wait_job(api: Api, job_id: str) -> Json:
    end = time.monotonic() + 30
    while time.monotonic() < end:
        job: Json = api.get(f"/jobs/{job_id}")
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError("job still running")


@pytest.fixture
def setup(api: Api, series: Json, book: Json, graph: Callable[[], Json]) -> Json:
    """start → left (gives rope) | right → gate → end; offline model for every role."""
    sid = series["id"]
    provider = api.post(
        "/llm/providers",
        {"name": "Offline", "kind": "fake", "models": [{"id": "offline"}]},
    )
    api.put(
        f"/series/{sid}/writing-settings",
        {"roles": {"writer": {"provider_id": provider["id"], "model": "offline"}}},
    )
    api.post(f"/series/{sid}/items", {"name": "Rope"})
    start = graph()["nodes"][0]
    act = start["act_id"]

    def node(title: str, src: str | None = None) -> Json:
        body: Json = {"act_id": act, "title": title}
        if src:
            body["link_from"] = {"node_id": src, "label": f"To {title}"}
        n: Json = api.post(f"/books/{book['id']}/nodes", body)
        return n

    left, right = node("Left", start["id"]), node("Right", start["id"])
    api.patch(f"/nodes/{left['id']}", {"on_enter": [{"op": "give", "item": "rope"}]})
    gate = node("Gate", left["id"])
    api.post(f"/nodes/{right['id']}/choices", {"label": "On", "target_node_id": gate["id"]})
    end = node("End", gate["id"])
    api.patch(f"/nodes/{end['id']}", {"ending_kind": "victory"})
    variants = {n["id"]: n["variants"][0]["id"] for n in graph()["nodes"]}
    return {
        "series_id": sid,
        "book_id": book["id"],
        "act_id": act,
        "start": start["id"],
        "gate": gate["id"],
        "end": end["id"],
        "v_gate": variants[gate["id"]],
        "v_start": variants[start["id"]],
    }


def test_consistency_findings_reach_problems(api: Api, setup: Json) -> None:
    api.post(
        f"/variants/{setup['v_gate']}/prose",
        {"text": "You tie your rope to the gate and climb. The wind howls.", "approve": True},
    )
    job = wait_job(api, api.post(f"/nodes/{setup['gate']}/consistency", None)["id"])
    assert job["status"] == "done", job
    assert job["result"]["issues"] == 1
    items = api.get(f"/books/{setup['book_id']}/assist?kind=finding&status=open")
    assert len(items) == 1
    f = items[0]
    assert f["node_id"] == setup["gate"]
    assert not f["outdated"]
    assert "rope" in f["payload"]["quote"].lower()
    assert f["payload"]["category"] == "path_validity"
    problems = api.get(f"/books/{setup['book_id']}/problems")["problems"]
    assert any(p["code"] == "consistency" and p["node_id"] == setup["gate"] for p in problems)

    # Rewriting the prose makes the finding outdated: it leaves Problems.
    api.post(f"/variants/{setup['v_gate']}/prose", {"text": "The wind howls.", "approve": True})
    assert api.get(f"/books/{setup['book_id']}/assist?kind=finding")[0]["outdated"] is True
    problems = api.get(f"/books/{setup['book_id']}/problems")["problems"]
    assert not any(p["code"] == "consistency" for p in problems)

    # Re-checking supersedes; dismissing hides it.
    api.post(
        f"/variants/{setup['v_gate']}/prose", {"text": "Rope in hand, you climb.", "approve": True}
    )
    wait_job(api, api.post(f"/books/{setup['book_id']}/consistency", {})["id"])
    open_items = api.get(f"/books/{setup['book_id']}/assist?kind=finding&status=open")
    assert len(open_items) == 1
    api.patch(f"/assist/{open_items[0]['id']}", {"status": "dismissed"})
    problems = api.get(f"/books/{setup['book_id']}/problems")["problems"]
    assert not any(p["code"] == "consistency" for p in problems)


def test_consistency_needs_prose(api: Api, setup: Json) -> None:
    err = api.post(f"/books/{setup['book_id']}/consistency", {}, expect=422)
    assert "no section here has prose" in err["detail"]


def test_suggested_subgraph_is_accepted_piecemeal(api: Api, setup: Json) -> None:
    act = setup["act_id"]
    api.post(f"/acts/{act}/beats", {"title": "Arrival", "node_ids": [setup["start"]]})
    api.post(f"/acts/{act}/beats", {"title": "Ambush", "description": "Bandits strike."})
    job = wait_job(api, api.post(f"/acts/{act}/suggest", {"notes": "Keep it short"})["id"])
    assert job["status"] == "done", job
    item = api.get(f"/books/{setup['book_id']}/assist?kind=suggestion&status=open")[0]
    p = item["payload"]
    assert [n["title"] for n in p["nodes"]] == ["Ambush"]
    assert p["nodes"][0]["beat_notes"] == "Bandits strike."
    assert len(p["choices"]) == 2  # into the new section, and on to the ending
    assert p["notes"] == "Keep it short"

    # Accepting the choice into it brings the new section along.
    into = next(i for i, c in enumerate(p["choices"]) if c["to"] == "new1")
    accepted = api.post(f"/assist/{item['id']}/accept-suggestion", {"choices": [into]}, expect=200)
    assert accepted["status"] == "partial"
    new_id = accepted["payload"]["nodes"][0]["node_id"]
    g = api.get(f"/books/{setup['book_id']}/graph")
    ambush = next(n for n in g["nodes"] if n["id"] == new_id)
    assert ambush["beat_notes"] == "Bandits strike."
    others = [n for n in g["nodes"] if n["id"] != new_id]
    assert not any(
        abs(n["x"] - ambush["x"]) < 260 and abs(n["y"] - ambush["y"]) < 130 for n in others
    )  # placed clear of existing cards
    assert any(
        o["target_node_id"] == new_id
        for n in g["nodes"]
        for c in n["choices"]
        for o in c["outcomes"]
    )
    done = api.post(f"/assist/{item['id']}/reject-suggestion", {}, expect=200)
    assert done["status"] == "accepted"
    api.post(f"/assist/{item['id']}/accept-suggestion", {}, expect=409)

    # One undo removes everything the acceptance added.
    api.post(f"/books/{setup['book_id']}/undo", None, expect=200)
    assert new_id not in {n["id"] for n in api.get(f"/books/{setup['book_id']}/graph")["nodes"]}


def test_suggester_output_is_validated(api: Api, setup: Json) -> None:
    fake.SCRIPT["suggester"].append(
        '{"nodes": [{"ref": "a", "title": "Cave"}, {"ref": "a", "title": "Dup"}, {"title": "no ref"}],'
        ' "choices": [{"from": "start", "to": "a", "label": "Enter"},'
        ' {"from": "start", "to": "ghost"}, {"from": "start", "to": "end"}]}'
    )
    wait_job(api, api.post(f"/acts/{setup['act_id']}/suggest", {})["id"])
    p = api.get(f"/books/{setup['book_id']}/assist?kind=suggestion")[0]["payload"]
    assert [n["title"] for n in p["nodes"]] == ["Cave"]
    assert [(c["from"], c["to"]) for c in p["choices"]] == [("start", "a")]


def test_lore_extraction_creates_and_updates(api: Api, setup: Json) -> None:
    sid = setup["series_id"]
    mara = api.post(f"/series/{sid}/characters", {"name": "Mara", "notes": "A witch."})
    api.post(
        f"/variants/{setup['v_start']}/prose",
        {
            "text": "A woman named Mara waits by the arch called the Iron Gate. She hums.",
            "approve": True,
        },
    )
    job = wait_job(api, api.post(f"/books/{setup['book_id']}/extract-lore", {})["id"])
    assert job["status"] == "done", job
    assert job["result"]["drafts"] == 2
    drafts = api.get(f"/books/{setup['book_id']}/assist?kind=lore&status=open")
    by_target = {d["payload"]["target"]: d for d in drafts}
    char, place = by_target["character"], by_target["lore"]
    assert char["payload"]["existing_id"] == mara["id"]
    assert place["payload"]["existing_id"] is None
    assert place["payload"]["fields"]["type"] == "location"

    # Extracting again doesn't duplicate open drafts.
    wait_job(api, api.post(f"/books/{setup['book_id']}/extract-lore", {})["id"])
    assert len(api.get(f"/books/{setup['book_id']}/assist?kind=lore&status=open")) == 2

    api.post(f"/assist/{char['id']}/accept-lore", {}, expect=200)
    updated = api.get(f"/characters/{mara['id']}")
    assert updated["notes"].startswith("A witch.\n\n")
    assert "Mara waits" in updated["notes"]

    api.post(
        f"/assist/{place['id']}/accept-lore",
        {"fields": {"body": "An arch of black iron."}},
        expect=200,
    )
    gate = next(x for x in api.get(f"/series/{sid}/lore") if x["name"] == "Iron Gate")
    assert gate["type"] == "location"
    assert gate["body"] == "An arch of black iron."
    api.post(f"/assist/{place['id']}/accept-lore", {}, expect=409)


def test_assists_need_models_and_prose(api: Api, series: Json, book: Json) -> None:
    api.post(f"/books/{book['id']}/extract-lore", {}, expect=422)


def test_accepting_lore_only_writes_allowed_fields(api: Api, setup: Json) -> None:
    sid = setup["series_id"]
    mara = api.post(f"/series/{sid}/characters", {"name": "Mara", "notes": "A witch."})
    api.post(
        f"/variants/{setup['v_start']}/prose",
        {"text": "A woman named Mara waits by the arch called the Iron Gate.", "approve": True},
    )
    wait_job(api, api.post(f"/books/{setup['book_id']}/extract-lore", {})["id"])
    drafts = api.get(f"/books/{setup['book_id']}/assist?kind=lore&status=open")
    by_target = {d["payload"]["target"]: d for d in drafts}
    # Anything outside the entity's text fields is ignored, never written.
    api.post(
        f"/assist/{by_target['character']['id']}/accept-lore",
        {"fields": {"key": "hijacked", "series_id": "x", "book_id": "y", "notes": "Hums."}},
        expect=200,
    )
    after = api.get(f"/characters/{mara['id']}")
    assert (after["key"], after["series_id"]) == (mara["key"], sid)
    assert after["name"] == "Mara"
    assert after["notes"] == "A witch.\n\nHums."


def test_lore_draft_for_a_deleted_entry_conflicts(api: Api, setup: Json) -> None:
    sid = setup["series_id"]
    gate = api.post(f"/series/{sid}/lore", {"name": "Iron Gate", "type": "location"})
    api.post(
        f"/variants/{setup['v_start']}/prose",
        {"text": "You reach the arch called the Iron Gate.", "approve": True},
    )
    wait_job(api, api.post(f"/books/{setup['book_id']}/extract-lore", {})["id"])
    (draft,) = api.get(f"/books/{setup['book_id']}/assist?kind=lore&status=open")
    assert draft["payload"]["existing_id"] == gate["id"]
    api.delete(f"/lore/{gate['id']}")
    api.post(f"/assist/{draft['id']}/accept-lore", {}, expect=409)


def test_lore_extraction_ignores_other_books_entries(api: Api, setup: Json, series: Json) -> None:
    sid = setup["series_id"]
    other = api.post(f"/series/{sid}/books", {"title": "Book Two"})
    api.post(f"/series/{sid}/characters", {"name": "Mara", "book_id": other["id"]})
    api.post(
        f"/variants/{setup['v_start']}/prose",
        {"text": "A woman named Mara waits.", "approve": True},
    )
    wait_job(api, api.post(f"/books/{setup['book_id']}/extract-lore", {})["id"])
    (draft,) = api.get(f"/books/{setup['book_id']}/assist?kind=lore&status=open")
    assert draft["payload"]["existing_id"] is None  # a new character, not Book Two's
    other_act = api.get(f"/books/{other['id']}/graph")["acts"][0]["id"]
    api.post(f"/books/{setup['book_id']}/extract-lore", {"act_id": other_act}, expect=422)


def test_assists_for_deleted_sections_and_acts_drop_out(
    api: Api, setup: Json, graph: Callable[[], Json]
) -> None:
    api.post(
        f"/variants/{setup['v_gate']}/prose",
        {"text": "You tie your rope to the gate and climb.", "approve": True},
    )
    wait_job(api, api.post(f"/nodes/{setup['gate']}/consistency", {})["id"])
    assert api.get(f"/books/{setup['book_id']}/assist?kind=finding")
    api.delete(f"/nodes/{setup['gate']}")
    assert api.get(f"/books/{setup['book_id']}/assist?kind=finding") == []

    act = api.post(f"/books/{setup['book_id']}/acts", {"title": "Act Two"})
    api.post(f"/acts/{act['id']}/beats", {"title": "Ambush", "description": "Bandits."})
    wait_job(api, api.post(f"/acts/{act['id']}/suggest", {})["id"])
    (item,) = api.get(f"/books/{setup['book_id']}/assist?kind=suggestion&status=open")
    api.delete(f"/acts/{act['id']}?force=true")
    assert api.get(f"/books/{setup['book_id']}/assist?kind=suggestion&status=open") == []
    api.post(f"/assist/{item['id']}/accept-suggestion", {}, expect=409)
