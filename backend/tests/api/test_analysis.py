"""Validation endpoint, gbx tooling and RefIndex consistency."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select

from gamebook.db.models import RefIndex
from gamebook.services import refs

from .conftest import Api, Json


def codes(api: Api, book_id: str) -> list[str]:
    return [p["code"] for p in api.get(f"/books/{book_id}/problems")["problems"]]


def test_problems_endpoint(api: Api, book: Json, graph: Callable[[], Json]) -> None:
    res = api.get(f"/books/{book['id']}/problems")
    # A fresh book: the start node is a dead end and there are no endings yet.
    assert res["counts"] == {"errors": 0, "warnings": 2, "info": 0}
    assert {p["code"] for p in res["problems"]} == {"dead_end", "no_endings"}

    start = graph()["nodes"][0]
    api.post(f"/nodes/{start['id']}/choices", {"label": "Climb", "condition": "has(rope)"})
    found = codes(api, book["id"])
    assert "gbx.ref" in found  # unknown item
    assert "outcome_no_target" in found

    end = api.post(f"/books/{book['id']}/nodes", {"act_id": start["act_id"], "title": "End"})
    api.patch(f"/nodes/{end['id']}", {"ending_kind": "victory"})
    choice = api.get(f"/nodes/{start['id']}")["choices"][0]
    api.patch(f"/choices/{choice['id']}", {"target_node_id": end["id"], "condition": None})
    assert api.get(f"/books/{book['id']}/problems")["counts"]["errors"] == 0


def test_rule_system_switch_affects_validation(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    start = graph()["nodes"][0]
    api.patch(
        f"/nodes/{start['id']}", {"on_enter": [{"op": "modify", "stat": "MANA", "amount": "1"}]}
    )
    assert "unknown_stat" in codes(api, book["id"])

    definition = api.get(f"/series/{series['id']}/rule-systems")[0]["definition"]
    definition["tiers"][0]["stats"].append({"key": "MANA", "label": "Mana", "initial": "5"})
    custom = api.post(
        f"/series/{series['id']}/rule-systems",
        {"name": "Magic", "definition": definition, "is_active": True},
    )
    assert custom["is_active"]
    assert [
        rs["is_active"]
        for rs in api.get(f"/series/{series['id']}/rule-systems")
        if rs["id"] != custom["id"]
    ] == [False]
    assert "unknown_stat" not in codes(api, book["id"])

    api.patch(f"/rule-systems/{custom['id']}", {"definition": {"tiers": []}}, expect=422)
    api.delete(f"/rule-systems/{custom['id']}")
    assert "no_rules" in codes(api, book["id"])


def test_gbx_check(api: Api, series: Json, book: Json) -> None:
    api.post(f"/series/{series['id']}/items", {"name": "Silver Key"})
    ok = api.post(
        "/gbx/check",
        {"source": "has(silver_key)  and GOLD>=5", "context": "condition", "book_id": book["id"]},
        expect=200,
    )
    assert ok["ok"]
    assert ok["normalized"] == "has(silver_key) and GOLD >= 5"
    assert ok["english"] == "you have the Silver Key and your Gold is at least 5"

    dice = api.post(
        "/gbx/check", {"source": "2d6", "context": "roll", "series_id": series["id"]}, expect=200
    )
    assert dice["range"] == [2, 12]
    assert abs(dice["distribution"]["7"] - 6 / 36) < 1e-9

    bad = api.post(
        "/gbx/check",
        {"source": "has(sword", "context": "condition", "book_id": book["id"]},
        expect=200,
    )
    assert not bad["ok"]
    assert bad["diagnostics"][0]["code"] == "syntax"

    tiered = api.post(
        "/gbx/check",
        {"source": "skill(TRACKING)", "context": "condition", "book_id": book["id"]},
        expect=200,
    )
    assert not tiered["ok"]
    adv = api.post(
        "/gbx/check",
        {
            "source": "skill(TRACKING)",
            "context": "condition",
            "book_id": book["id"],
            "tier": "advanced",
        },
        expect=200,
    )
    assert adv["ok"]
    assert adv["english"] == "you have the skill of Tracking"
    api.post("/gbx/check", {"source": "1", "context": "roll"}, expect=422)


def _snapshot(client: TestClient, series_id: str) -> list[tuple[object, ...]]:
    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session() as s:
        return sorted(
            (
                r.source_type,
                r.source_id,
                r.target_type,
                r.target_key,
                r.target_id,
                r.role,
                r.field,
                r.qty,
            )
            for r in s.scalars(select(RefIndex).where(RefIndex.series_id == series_id))
        )


def test_incremental_index_matches_full_rebuild(
    client: TestClient, api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    sid = series["id"]
    start = graph()["nodes"][0]
    rope = api.post(f"/series/{sid}/items", {"name": "Rope"})
    orc = api.post(f"/series/{sid}/enemies", {"name": "Orc", "loot": [{"item": "rope"}]})
    hall = api.post(
        f"/books/{book['id']}/nodes",
        {"act_id": start["act_id"], "title": "Hall", "link_from": {"node_id": start["id"]}},
    )
    api.put(f"/nodes/{hall['id']}/items", [{"item_id": rope["id"]}])
    enc = api.post(f"/nodes/{hall['id']}/encounters", {"enemies": [{"enemy_id": orc["id"]}]})
    api.post(
        f"/nodes/{hall['id']}/choices",
        {"kind": "combat", "encounter_id": enc["id"], "condition": "flag(X)"},
    )
    api.post(f"/nodes/{hall['id']}/variants", {"condition": "visits(hall) > 1 and has(rope)"})
    # Mentions an item before it exists; creating it must resolve the ref.
    api.patch(f"/nodes/{start['id']}", {"on_enter": [{"op": "give", "item": "lantern"}]})
    api.post(f"/series/{sid}/items", {"name": "Lantern"})
    api.patch(f"/items/{rope['id']}", {"key": "cord"})
    api.patch(f"/nodes/{hall['id']}", {"key": "great_hall"})

    incremental = _snapshot(client, sid)
    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session() as s:
        refs.rebuild_series(s, sid)
    assert _snapshot(client, sid) == incremental
    lantern = [r for r in incremental if r[3] == "lantern"]
    assert lantern
    assert all(r[4] is not None for r in lantern)
