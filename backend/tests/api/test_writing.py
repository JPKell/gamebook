"""Phase 7 API: providers, templates, context, the prose pipeline, review and staleness."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from gamebook.llm import fake

from .conftest import Api, Json


@pytest.fixture(autouse=True)
def clear_script() -> Iterator[None]:
    fake.SCRIPT.clear()
    yield
    fake.SCRIPT.clear()


def wait_job(api: Api, job_id: str, timeout: float = 30) -> Json:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job: Json = api.get(f"/jobs/{job_id}")
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError("job still running")


@pytest.fixture
def setup(api: Api, series: Json, book: Json, graph: Callable[[], Json]) -> Json:
    """A two-section book wired to the offline model with priced tokens."""
    sid = series["id"]
    provider = api.post(
        "/llm/providers",
        {
            "name": "Offline",
            "kind": "fake",
            "models": [{"id": "offline", "input_per_mtok": 1.0, "output_per_mtok": 2.0}],
        },
    )
    api.put(
        f"/series/{sid}/writing-settings",
        {
            "roles": {"writer": {"provider_id": provider["id"], "model": "offline"}},
            "pass_threshold": 7.5,
            "max_iterations": 2,
        },
    )
    mara = api.post(f"/series/{sid}/characters", {"name": "Mara", "role": "Witch", "voice": "Dry."})
    crypt = api.post(
        f"/series/{sid}/lore", {"name": "Crypt", "type": "location", "body": "Cold stone."}
    )
    start = graph()["nodes"][0]
    api.patch(
        f"/nodes/{start['id']}",
        {
            "beat_notes": "A raven lands on the gate. [[mara]] watches from the dark.",
            "on_enter": [{"op": "set_flag", "flag": "RAVEN"}],
            "character_ids": [mara["id"]],
            "location_id": crypt["id"],
        },
    )
    api.patch(f"/acts/{start['act_id']}", {"summary": "Arrival at the crypt."})
    hall = api.post(
        f"/books/{book['id']}/nodes",
        {
            "act_id": start["act_id"],
            "title": "Hall",
            "link_from": {"node_id": start["id"], "label": "Enter the hall"},
        },
    )
    api.patch(f"/nodes/{hall['id']}", {"beat_notes": "Dust and silence."})
    g = graph()
    variant = {n["id"]: n["variants"][0]["id"] for n in g["nodes"]}
    return {
        "series_id": sid,
        "book_id": book["id"],
        "act_id": start["act_id"],
        "start": start["id"],
        "hall": hall["id"],
        "v_start": variant[start["id"]],
        "v_hall": variant[hall["id"]],
        "provider": provider["id"],
    }


def generate(api: Api, variant_id: str, **body: Any) -> Json:
    job = api.post(f"/variants/{variant_id}/generate", body)
    return wait_job(api, job["id"])


# ── providers & templates ────────────────────────────────────────────────


def test_providers(api: Api, setup: Json) -> None:
    api.post("/llm/providers", {"name": "Bad", "kind": "openai"}, expect=422)
    api.post("/llm/providers", {"name": "Bad", "base_url": "ftp://x"}, expect=422)
    local = api.post(
        "/llm/providers",
        {"name": "Local", "base_url": "http://127.0.0.1:9/v1", "api_key_env": "GB_NOPE_KEY"},
    )
    assert local["api_key_present"] is False
    test = api.post(f"/llm/providers/{local['id']}/test", None, expect=200)
    assert test["ok"] is False
    assert "GB_NOPE_KEY" in test["message"]
    assert api.post(f"/llm/providers/{setup['provider']}/test", None, expect=200)["ok"] is True
    api.delete(f"/llm/providers/{setup['provider']}", expect=409)  # in use
    api.patch(f"/llm/providers/{local['id']}", {"max_concurrency": 4})
    api.delete(f"/llm/providers/{local['id']}")


def test_templates_are_versioned(api: Api, setup: Json) -> None:
    tpls = api.get("/llm/templates")
    assert {t["role"] for t in tpls if t["is_active"]} == {
        "writer",
        "critic",
        "editor",
        "summarizer",
        "consistency",
        "suggester",
        "lore_extractor",
        "player",
    }
    writer = next(t for t in tpls if t["role"] == "writer")
    v2 = api.post("/llm/templates/writer", {"system": "Be brief.", "user": "{{ ctx.node.title }}"})
    assert (v2["version"], v2["is_active"]) == (2, True)
    api.post("/llm/templates/writer", {"system": "{% if %}", "user": "x"}, expect=422)
    preview = api.post(
        "/llm/templates/writer/preview", {"variant_id": setup["v_start"]}, expect=200
    )
    assert preview["user"] == "Start"
    bad = api.post(
        "/llm/templates/writer/preview",
        {"variant_id": setup["v_start"], "user": "{{ ctx.nope.missing }}"},
        expect=200,
    )
    assert bad["error"]
    api.post(f"/llm/templates/{writer['id']}/activate", None, expect=200)
    full = api.post("/llm/templates/writer/preview", {"variant_id": setup["v_start"]}, expect=200)
    assert "A raven lands on the gate." in full["user"]
    assert "Enter the hall" in full["user"]


def test_context(api: Api, setup: Json) -> None:
    c = api.get(f"/variants/{setup['v_start']}/context")
    ctx = c["ctx"]
    assert ctx["node"]["beat_notes"].startswith("A raven")
    assert ctx["choices"] == ["Enter the hall"]
    assert ctx["location"]["name"] == "Crypt"
    assert ctx["characters"][0]["name"] == "Mara"
    assert ctx["mentioned"][0]["name"] == "Mara"
    assert ctx["act"]["summary"] == "Arrival at the crypt."
    assert c["tokens"] > 0
    assert c["trimmed"] == []
    hall = api.get(f"/variants/{setup['v_hall']}/context")["ctx"]
    assert "RAVEN" in hall["digest"]["must_text"]
    assert hall["previous_title"] == "Start"
    assert hall["previous_text"] is None  # nothing written yet


def test_tight_budget_trims_low_priority_context(api: Api, setup: Json) -> None:
    sid = setup["series_id"]
    lore = api.get(f"/series/{sid}/lore")[0]
    api.patch(f"/lore/{lore['id']}", {"body": "Stone. " * 400})
    settings = api.get(f"/series/{sid}/writing-settings")
    api.put(f"/series/{sid}/writing-settings", {**settings, "context_tokens": 500})
    c = api.get(f"/variants/{setup['v_start']}/context")
    assert "location text" in c["trimmed"] or "mentioned" in c["trimmed"]
    assert c["ctx"]["node"]["beat_notes"].startswith("A raven")  # never cut


# ── pipeline ─────────────────────────────────────────────────────────────


def test_writer_critic_editor_loop(api: Api, setup: Json) -> None:
    job = generate(api, setup["v_start"], notes="Make it eerie.")
    assert job["status"] == "done", job
    run = api.get(f"/pipeline-runs/{job['result']['pipeline_run_id']}")
    assert [t["kind"] for t in run["trail"]] == ["draft", "critique", "edit", "critique"]
    assert run["iterations"] == 1
    assert run["final_score"] == 8
    assert run["notes"] == "Make it eerie."
    assert run["cost_usd"] > 0

    prose = api.get(f"/nodes/{setup['start']}/prose")["variants"][0]
    assert prose["status"] == "in_review"
    assert prose["latest"]["source"] == "llm"
    assert "raven" in prose["latest"]["text"].lower()
    assert prose["latest"]["summary"]

    calls = api.get(f"/llm/calls?pipeline_run_id={run['id']}")["calls"]
    assert sorted(c["role"] for c in calls) == [
        "critic",
        "critic",
        "editor",
        "summarizer",
        "writer",
    ]
    assert all(c["status"] == "ok" and c["template_version"] == 1 for c in calls)
    detail = api.get(f"/llm/calls/{calls[0]['id']}")
    assert detail["messages"][0]["role"] == "system"
    assert detail["response"]
    costs = api.get(f"/llm/costs?series_id={setup['series_id']}")
    assert costs["total_usd"] == pytest.approx(run["cost_usd"], abs=1e-6)
    assert {r["key"] for r in costs["by_role"]} == {"writer", "critic", "editor", "summarizer"}


def test_threshold_skips_editing(api: Api, setup: Json) -> None:
    sid = setup["series_id"]
    settings = api.get(f"/series/{sid}/writing-settings")
    api.put(f"/series/{sid}/writing-settings", {**settings, "pass_threshold": 5})
    job = generate(api, setup["v_start"])
    run = api.get(f"/pipeline-runs/{job['result']['pipeline_run_id']}")
    assert [t["kind"] for t in run["trail"]] == ["draft", "critique"]


def test_bad_critic_json_is_retried_once(api: Api, setup: Json) -> None:
    fake.SCRIPT["critic"] += ["I liked it, 9/10!", '{"overall": 9, "scores": {}, "issues": []}']
    job = generate(api, setup["v_start"])
    assert job["status"] == "done"
    calls = api.get(f"/llm/calls?pipeline_run_id={job['result']['pipeline_run_id']}&role=critic")
    assert calls["total"] == 2
    fake.SCRIPT["critic"] += ["nope", "still nope"]
    failed = generate(api, setup["v_start"])
    assert failed["status"] == "failed"
    assert "valid JSON" in failed["error"]


def test_generate_needs_a_model(api: Api, setup: Json) -> None:
    api.put(f"/series/{setup['series_id']}/writing-settings", {"roles": {}})
    err = api.post(f"/variants/{setup['v_start']}/generate", {}, expect=422)
    assert "No model is set" in err["detail"]


# ── review & staleness ───────────────────────────────────────────────────


def test_review_approve_reject_and_stale(api: Api, setup: Json) -> None:
    job = generate(api, setup["v_start"])
    pid = job["result"]["prose_id"]
    approved = api.post(f"/prose/{pid}/approve", {}, expect=200)
    assert approved["status"] == "approved"
    v = api.get(f"/nodes/{setup['start']}/prose")["variants"][0]
    assert v["status"] == "approved"

    # Changing the beat notes makes the approved text stale.
    api.patch(f"/nodes/{setup['start']}", {"beat_notes": "A crow, not a raven."})
    assert api.get(f"/nodes/{setup['start']}/prose")["variants"][0]["status"] == "stale"
    queue = api.get(f"/books/{setup['book_id']}/writing-queue")
    assert queue["counts"]["stale"] == 1
    problems = api.get(f"/books/{setup['book_id']}/problems")["problems"]
    assert any(p["code"] == "prose_stale" and p["node_id"] == setup["start"] for p in problems)

    # Approving with edits saves a human version and supersedes the old one.
    edited = api.post(f"/prose/{pid}/approve", {"text": "A crow lands. Silence."}, expect=200)
    assert edited["source"] == "human"
    assert edited["parent_id"] == pid
    assert edited["summary"] == "A crow lands. Silence."
    versions = api.get(f"/nodes/{setup['start']}/prose")["variants"][0]["versions"]
    assert [x["status"] for x in versions] == ["approved", "superseded"]
    assert api.get(f"/nodes/{setup['start']}/prose")["variants"][0]["status"] == "approved"

    # The next section is stale once its predecessor's approved text changes.
    hall = api.post(f"/variants/{setup['v_hall']}/prose", {"text": "Dusty.", "approve": True})
    assert hall["status"] == "approved"
    assert "A crow lands" in api.get(f"/variants/{setup['v_hall']}/context")["ctx"]["previous_text"]
    api.post(
        f"/variants/{setup['v_start']}/prose", {"text": "A crow lands. It caws.", "approve": True}
    )
    assert api.get(f"/nodes/{setup['hall']}/prose")["variants"][0]["status"] == "stale"

    draft = generate(api, setup["v_hall"])
    rejected = api.post(
        f"/prose/{draft['result']['prose_id']}/reject", {"notes": "Too long"}, expect=200
    )
    assert rejected["status"] == "rejected"
    # An older (rejected or superseded) version can be brought back: as a new version.
    restored = api.post(f"/prose/{rejected['id']}/approve", {}, expect=200)
    assert restored["id"] != rejected["id"]
    assert restored["parent_id"] == rejected["id"]
    assert restored["text"] == rejected["text"]
    assert restored["summary"] == rejected["summary"]
    api.put(f"/prose/{hall['id']}/summary", {"summary": "The hall is dusty."}, expect=200)
    story = api.get(f"/variants/{setup['v_hall']}/context")
    assert story["ctx"]["previous_title"] == "Start"


def test_generate_act_in_canonical_order(api: Api, setup: Json) -> None:
    job = api.post(f"/acts/{setup['act_id']}/generate", {"only": "missing"})
    done = wait_job(api, job["id"])
    assert done["status"] == "done", done
    assert done["result"]["written"] == 2
    assert done["result"]["failed"] == []
    queue = api.get(f"/books/{setup['book_id']}/writing-queue")
    assert [r["node_id"] for r in queue["rows"]] == [setup["start"], setup["hall"]]
    assert queue["counts"]["in_review"] == 2
    # The second section was written after (and with) the first one's draft.
    hall_run = api.get(f"/nodes/{setup['hall']}/prose")["variants"][0]["latest"]["pipeline_run_id"]
    writer_call = api.get(f"/llm/calls?pipeline_run_id={hall_run}&role=writer")["calls"][0]
    assert (
        "(unapproved draft)" in api.get(f"/llm/calls/{writer_call['id']}")["messages"][1]["content"]
    )
    api.post(f"/acts/{setup['act_id']}/generate", {"only": "stale"}, expect=422)
    capped = api.post(f"/acts/{setup['act_id']}/generate", {"only": "all", "max_cost_usd": 0})
    assert wait_job(api, capped["id"])["result"]["stopped"].startswith(
        "Stopped at the $0.00 budget"
    )


# ── review regressions ───────────────────────────────────────────────────


def test_context_that_cannot_fit_still_returns(api: Api, setup: Json) -> None:
    """Review: trimming looped forever when the untrimmable parts exceed the budget."""
    sid = setup["series_id"]
    api.post(f"/variants/{setup['v_start']}/prose", {"text": "Short.", "approve": True})
    api.patch(f"/nodes/{setup['hall']}", {"beat_notes": "word " * 4000})
    settings = api.get(f"/series/{sid}/writing-settings")
    api.put(f"/series/{sid}/writing-settings", {**settings, "context_tokens": 500})
    c = api.get(f"/variants/{setup['v_hall']}/context")
    assert c["ctx"]["previous_text"] is None
    assert "previous section (start)" in c["trimmed"]
    api.get(f"/books/{setup['book_id']}/problems")


def test_roles_without_a_provider_use_the_writers(api: Api, setup: Json) -> None:
    """Review: tuning the critic's temperature alone broke every generation."""
    sid = setup["series_id"]
    settings = api.get(f"/series/{sid}/writing-settings")
    settings["roles"]["critic"] = {"temperature": 0.1, "max_tokens": 300}
    api.put(f"/series/{sid}/writing-settings", settings)
    assert generate(api, setup["v_start"])["status"] == "done"


def test_json_retry_cost_is_counted(api: Api, setup: Json) -> None:
    fake.SCRIPT["critic"] += ["not json at all", '{"overall": 9, "issues": null}']
    job = generate(api, setup["v_start"])
    assert job["status"] == "done", job
    run = api.get(f"/pipeline-runs/{job['result']['pipeline_run_id']}")
    calls = api.get(f"/llm/calls?pipeline_run_id={run['id']}")["calls"]
    assert run["cost_usd"] == pytest.approx(sum(c["cost_usd"] for c in calls), abs=1e-6)
    retry = next(c for c in calls if c["role"] == "critic" and c["prompt_tokens"] > 0)
    detail = api.get(f"/llm/calls/{calls[-1]['id']}")
    assert detail["messages"]  # logged
    retried = [api.get(f"/llm/calls/{c['id']}")["messages"] for c in calls if c["role"] == "critic"]
    assert any(
        m[-2]["role"] == "assistant" and m[-2]["content"] == "not json at all" for m in retried
    )
    del retry


def test_approving_a_draft_unchanged_keeps_successors_fresh(api: Api, setup: Json) -> None:
    """Review: the predecessor's draft text leaked into the successor's staleness hash."""
    draft = api.post(f"/variants/{setup['v_start']}/prose", {"text": "A raven waits."})
    api.post(f"/variants/{setup['v_hall']}/prose", {"text": "Dust.", "approve": True})
    api.post(f"/prose/{draft['id']}/approve", {}, expect=200)
    hall = api.get(f"/nodes/{setup['hall']}/prose")["variants"][0]
    assert hall["status"] == "approved"


def test_a_section_cannot_be_generated_twice_at_once(api: Api, setup: Json) -> None:
    from gamebook.db.models import Job

    first = api.post(f"/variants/{setup['v_start']}/generate", {})
    db = api.c.app.state.db  # type: ignore[attr-defined]
    with db.session() as s:  # pretend it's still running
        s.get_one(Job, first["id"]).status = "running"
    wait = time.monotonic() + 5
    while time.monotonic() < wait:
        with db.session() as s:
            if s.get_one(Job, first["id"]).status != "running":
                s.get_one(Job, first["id"]).status = "running"
                break
        time.sleep(0.05)
    api.post(f"/variants/{setup['v_start']}/generate", {}, expect=409)
    api.post(f"/acts/{setup['act_id']}/generate", {"only": "all"}, expect=409)


def test_secret_headers_are_masked(api: Api) -> None:
    p = api.post(
        "/llm/providers",
        {
            "name": "Proxy",
            "base_url": "http://127.0.0.1:9/v1",
            "headers": {"X-Title": "Gamebook", "X-Api-Key": "sk-secret"},
        },
    )
    assert p["headers"] == {"X-Title": "Gamebook", "X-Api-Key": "********"}
    api.patch(f"/llm/providers/{p['id']}", {"headers": {**p["headers"], "X-Title": "GB"}})
    from gamebook.db.models import LlmProvider

    with api.c.app.state.db.session() as s:  # type: ignore[attr-defined]
        assert s.get_one(LlmProvider, p["id"]).headers == {
            "X-Title": "GB",
            "X-Api-Key": "sk-secret",
        }
    api.post(
        "/llm/providers", {"name": "X", "base_url": "http://x", "api_key_env": "HOME"}, expect=422
    )
    # A key pasted where the variable name goes is explained, and never echoed back.
    secret = "lc_MadeUpSecretValue123"
    res = api.c.patch(f"/api/llm/providers/{p['id']}", json={"api_key_env": secret})
    assert res.status_code == 422
    assert secret not in res.text
    assert "not the key itself" in res.text
    assert (
        api.patch(f"/llm/providers/{p['id']}", {"api_key_env": " GB_OK_KEY "})["api_key_env"]
        == "GB_OK_KEY"
    )
