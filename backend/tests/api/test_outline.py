"""Phase 6 API: story beats, wiki mentions and backlinks, and the state digest."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from .conftest import Api, Json


def _two_nodes(api: Api, book: Json, graph: Callable[[], Json]) -> tuple[Json, Json]:
    start = graph()["nodes"][0]
    hall = api.post(
        f"/books/{book['id']}/nodes",
        {"act_id": start["act_id"], "title": "Hall", "link_from": {"node_id": start["id"]}},
    )
    return start, hall


def test_beats_crud_order_and_undo(api: Api, book: Json, graph: Callable[[], Json]) -> None:
    start, hall = _two_nodes(api, book, graph)
    act = start["act_id"]
    a = api.post(f"/acts/{act}/beats", {"title": "Arrival", "node_ids": [start["id"]]})
    b = api.post(f"/acts/{act}/beats", {"title": "The hall"})
    assert (a["position"], b["position"]) == (0, 1)

    out = api.get(f"/books/{book['id']}/outline")
    beats = out["acts"][0]["beats"]
    assert [x["title"] for x in beats] == ["Arrival", "The hall"]
    assert beats[0]["node_ids"] == [start["id"]]

    api.patch(f"/beats/{b['id']}", {"node_ids": [hall["id"], hall["id"]], "description": "Dark"})
    order = api.put(f"/acts/{act}/beats/order", {"ids": [b["id"], a["id"]]})
    assert [x["id"] for x in order] == [b["id"], a["id"]]
    assert order[0]["node_ids"] == [hall["id"]]  # duplicates collapse
    api.put(f"/acts/{act}/beats/order", {"ids": [a["id"]]}, expect=422)

    api.delete(f"/beats/{a['id']}")
    assert [x["title"] for x in api.get(f"/books/{book['id']}/outline")["acts"][0]["beats"]] == [
        "The hall"
    ]
    api.post(f"/books/{book['id']}/undo", None, expect=200)
    restored = api.get(f"/books/{book['id']}/outline")["acts"][0]["beats"]
    assert {x["title"] for x in restored} == {"Arrival", "The hall"}

    # Deleting a node removes it from beats.
    api.delete(f"/nodes/{hall['id']}")
    hall_beat = next(
        x
        for x in api.get(f"/books/{book['id']}/outline")["acts"][0]["beats"]
        if x["title"] == "The hall"
    )
    assert hall_beat["node_ids"] == []


def test_beats_reject_nodes_from_other_books_and_acts(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    other = api.post(f"/series/{series['id']}/books", {"title": "Other"})
    other_start = api.get(f"/books/{other['id']}/graph")["nodes"][0]
    act = graph()["nodes"][0]["act_id"]
    api.post(f"/acts/{act}/beats", {"node_ids": [other_start["id"]]}, expect=422)


def test_beat_problems(api: Api, book: Json, graph: Callable[[], Json]) -> None:
    start, hall = _two_nodes(api, book, graph)

    def codes() -> set[str]:
        return {p["code"] for p in api.get(f"/books/{book['id']}/problems")["problems"]}

    assert not codes() & {"beat_empty", "node_no_beat"}  # no outline: quiet
    api.post(f"/acts/{start['act_id']}/beats", {"title": "Arrival", "node_ids": [start["id"]]})
    api.post(f"/acts/{start['act_id']}/beats", {"title": "Later"})
    found = {
        (p["code"], p["node_id"])
        for p in api.get(f"/books/{book['id']}/problems")["problems"]
        if p["code"] in ("beat_empty", "node_no_beat")
    }
    assert ("node_no_beat", hall["id"]) in found
    assert ("beat_empty", None) in found


def test_mentions_backlinks_and_renames(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    sid = series["id"]
    mara = api.post(f"/series/{sid}/characters", {"name": "Mara"})
    crypt = api.post(f"/series/{sid}/lore", {"name": "Crypt", "type": "location"})
    api.patch(
        f"/lore/{crypt['id']}", {"body": "Where [[mara|the witch]] hides. See [[lore:crypt]]."}
    )
    api.patch(f"/characters/{mara['id']}", {"secrets": "Fears the [[crypt]]."})
    start = graph()["nodes"][0]
    api.patch(f"/nodes/{start['id']}", {"beat_notes": "Mara ([[character:mara]]) waits."})
    api.post(f"/acts/{start['act_id']}/beats", {"title": "Meet", "description": "[[mara]] appears"})

    used = api.get(f"/series/{sid}/where-used?target_type=character&key=mara")["refs"]
    mentions = [r for r in used if r["role"] == "mention"]
    labels = {r["source_label"] or r["node_title"] for r in mentions}
    assert labels == {"Crypt", "Start", "Story beat: Meet"}

    crypt_used = api.get(f"/series/{sid}/where-used?target_type=lore&key=crypt")["refs"]
    assert {r["source_label"] for r in crypt_used if r["role"] == "mention"} == {"Mara", "Crypt"}

    # Renaming the character rewrites every mention (labels and prefixes kept).
    api.patch(f"/characters/{mara['id']}", {"key": "mara_vell"})
    assert api.get(f"/lore/{crypt['id']}")["body"] == (
        "Where [[mara_vell|the witch]] hides. See [[lore:crypt]]."
    )
    node = next(n for n in graph()["nodes"] if n["id"] == start["id"])
    assert node["beat_notes"] == "Mara ([[character:mara_vell]]) waits."
    beat = api.get(f"/books/{book['id']}/outline")["acts"][0]["beats"][0]
    assert beat["description"] == "[[mara_vell]] appears"


def test_digest_must_may_gates_and_canonical(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    sid = series["id"]
    api.post(f"/series/{sid}/items", {"name": "Silver Key", "category": "key"})
    api.post(f"/series/{sid}/items", {"name": "Rope"})
    mara = api.post(f"/series/{sid}/characters", {"name": "Mara"})
    start = graph()["nodes"][0]
    act = start["act_id"]
    api.patch(
        f"/nodes/{start['id']}",
        {"on_enter": [{"op": "set_flag", "flag": "RAVEN"}], "character_ids": [mara["id"]]},
    )
    left = api.post(
        f"/books/{book['id']}/nodes",
        {"act_id": act, "title": "Left", "link_from": {"node_id": start["id"]}},
    )
    api.patch(f"/nodes/{left['id']}", {"on_enter": [{"op": "give", "item": "rope"}]})
    right = api.post(
        f"/books/{book['id']}/nodes",
        {"act_id": act, "title": "Right", "link_from": {"node_id": start["id"]}},
    )
    gate = api.post(
        f"/books/{book['id']}/nodes",
        {"act_id": act, "title": "Gate", "link_from": {"node_id": left["id"]}},
    )
    api.post(f"/nodes/{right['id']}/choices", {"label": "On", "target_node_id": gate["id"]})
    end = api.post(f"/books/{book['id']}/nodes", {"act_id": act, "title": "End"})
    api.patch(f"/nodes/{end['id']}", {"ending_kind": "victory"})
    for label, cond in (
        ("Unlock", "has(silver_key)"),
        ("Climb", "has(rope)"),
        ("Call", "flag(RAVEN)"),
    ):
        api.post(
            f"/nodes/{gate['id']}/choices",
            {"label": label, "condition": cond, "target_node_id": end["id"]},
        )

    d = api.get(f"/nodes/{gate['id']}/digest")
    assert d["reachable"]
    assert (d["depth_min"], d["depth_max"]) == (2, 2)
    assert [f["key"] for f in d["must"]["flags"]] == ["RAVEN"]
    assert d["must"]["characters"] == [{"key": "mara", "label": "Mara"}]
    assert d["may"]["items"] == [{"key": "rope", "label": "Rope"}]
    assert {g["label"]: g["verdict"] for g in d["gates"]} == {
        "Unlock": "never",
        "Climb": "depends",
        "Call": "always",
    }
    assert d["canonical_predecessor_auto"] == left["id"]
    assert d["canonical_predecessor"] == left["id"]

    api.patch(f"/nodes/{gate['id']}", {"canonical_predecessor_id": right["id"]})
    d = api.get(f"/nodes/{gate['id']}/digest")
    assert d["canonical_predecessor"] == right["id"]
    assert d["canonical_predecessor_override"] == right["id"]

    problems = {
        (p["code"], p["choice_id"]) for p in api.get(f"/books/{book['id']}/problems")["problems"]
    }
    unlock = next(
        c["id"]
        for n in graph()["nodes"]
        if n["id"] == gate["id"]
        for c in n["choices"]
        if c["label"] == "Unlock"
    )
    assert ("gate_never", unlock) in problems

    whole = api.get(f"/books/{book['id']}/digest?tier=basic")
    assert whole["tier"] == "basic"
    assert set(whole["nodes"]) >= {gate["id"], end["id"]}
    api.get(f"/books/{book['id']}/digest?tier=legendary", expect=422)


def test_beats_reject_nodes_from_other_acts(
    api: Api, book: Json, graph: Callable[[], Json]
) -> None:
    act1 = graph()["nodes"][0]["act_id"]
    act2 = api.post(f"/books/{book['id']}/acts", {"title": "Two"})
    elsewhere = api.post(f"/books/{book['id']}/nodes", {"act_id": act2["id"], "title": "Far"})
    api.post(f"/acts/{act1}/beats", {"node_ids": [elsewhere["id"]]}, expect=422)


def test_mention_index_stays_fresh_through_undo_and_deletes(
    api: Api, client: TestClient, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    """Review regression: beat refs went stale on undo and act deletion; deleting a
    mentioned character crashed."""
    from .test_review_regressions import _assert_index_fresh

    sid = series["id"]
    mara = api.post(f"/series/{sid}/characters", {"name": "Mara"})
    crypt = api.post(f"/series/{sid}/lore", {"name": "Crypt", "body": "[[mara]] hides here"})
    act2 = api.post(f"/books/{book['id']}/acts", {"title": "Two"})
    beat = api.post(f"/acts/{act2['id']}/beats", {"title": "B", "description": "[[mara]]"})
    api.patch(f"/beats/{beat['id']}", {"description": "[[crypt]]"})
    api.post(f"/books/{book['id']}/undo", None, expect=200)
    _assert_index_fresh(client, sid)
    api.post(f"/books/{book['id']}/undo", None, expect=200)  # undo "Add story beat"
    _assert_index_fresh(client, sid)
    api.post(f"/books/{book['id']}/redo", None, expect=200)
    api.delete(f"/acts/{act2['id']}?force=true")
    _assert_index_fresh(client, sid)

    api.delete(f"/characters/{mara['id']}?force=true")  # mentioned in the lore body
    _assert_index_fresh(client, sid)
    api.delete(f"/lore/{crypt['id']}?force=true")
    _assert_index_fresh(client, sid)
    assert graph()["nodes"]
