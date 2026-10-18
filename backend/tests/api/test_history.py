"""Server-side undo/redo and checkpoints."""

from collections.abc import Callable

import pytest

from gamebook.services import history

from .conftest import Api, Json


def state(api: Api, book_id: str) -> Json:
    s: Json = api.get(f"/books/{book_id}/history")
    return s


def test_undo_redo_round_trip(api: Api, book: Json, graph: Callable[[], Json]) -> None:
    bid = book["id"]
    assert state(api, bid)["can_undo"] is False
    before = graph()
    start = before["nodes"][0]

    hall = api.post(
        f"/books/{bid}/nodes",
        {"act_id": start["act_id"], "title": "Hall", "link_from": {"node_id": start["id"]}},
    )
    api.patch(f"/nodes/{hall['id']}", {"beat_notes": "Echoes."})
    st = state(api, bid)
    assert st["can_undo"]
    assert st["undo_label"] == "Edit node 'Hall'"

    step = api.post(f"/books/{bid}/undo", expect=200)
    assert step["applied"] == "Edit node 'Hall'"
    assert api.get(f"/nodes/{hall['id']}")["beat_notes"] == ""

    api.post(f"/books/{bid}/undo", expect=200)  # undo "Add node"
    g = graph()
    assert [n["key"] for n in g["nodes"]] == ["start"]
    assert g["nodes"][0]["choices"] == []
    st = state(api, bid)
    assert (st["can_undo"], st["can_redo"], st["redo_label"]) == (False, True, "Add node 'Hall'")

    api.post(f"/books/{bid}/redo", expect=200)
    api.post(f"/books/{bid}/redo", expect=200)
    g = graph()
    hall_again = next(n for n in g["nodes"] if n["key"] == "hall")
    assert hall_again["id"] == hall["id"]  # identity preserved
    assert hall_again["beat_notes"] == "Echoes."
    start_again = next(n for n in g["nodes"] if n["key"] == "start")
    assert start_again["choices"][0]["outcomes"][0]["target_node_id"] == hall["id"]
    api.post(f"/books/{bid}/redo", expect=409)


def test_new_change_clears_redo(api: Api, book: Json, graph: Callable[[], Json]) -> None:
    bid = book["id"]
    start = graph()["nodes"][0]
    api.patch(f"/nodes/{start['id']}", {"title": "Gate"})
    api.post(f"/books/{bid}/undo", expect=200)
    assert state(api, bid)["can_redo"]
    api.patch(f"/nodes/{start['id']}", {"summary": "x"})
    assert not state(api, bid)["can_redo"]


def test_typing_coalesces(api: Api, book: Json, graph: Callable[[], Json]) -> None:
    bid = book["id"]
    start = graph()["nodes"][0]
    for text in ("Y", "Yo", "You", "You arrive"):
        api.patch(f"/nodes/{start['id']}", {"beat_notes": text})
    assert state(api, bid)["depth"] == 1
    api.post(f"/books/{bid}/undo", expect=200)
    assert api.get(f"/nodes/{start['id']}")["beat_notes"] == ""


def test_undo_delete_restores_everything(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    bid = book["id"]
    sid = series["id"]
    rope = api.post(f"/series/{sid}/items", {"name": "Rope"})
    orc = api.post(f"/series/{sid}/enemies", {"name": "Orc"})
    start = graph()["nodes"][0]
    hall = api.post(
        f"/books/{bid}/nodes",
        {"act_id": start["act_id"], "title": "Hall", "link_from": {"node_id": start["id"]}},
    )
    api.put(f"/nodes/{hall['id']}/items", [{"item_id": rope["id"], "qty": 3}])
    enc = api.post(
        f"/nodes/{hall['id']}/encounters", {"enemies": [{"enemy_id": orc["id"], "level": 2}]}
    )
    api.post(
        f"/nodes/{hall['id']}/choices",
        {"kind": "combat", "encounter_id": enc["id"], "condition": "has(rope)"},
    )
    before = graph()

    api.delete(f"/nodes/{hall['id']}")
    assert api.get(f"/nodes/{start['id']}")["choices"][0]["outcomes"][0]["target_node_id"] is None
    api.post(f"/books/{bid}/undo", expect=200)
    after = graph()

    def ids_free(g: Json) -> list[Json]:
        out = []
        for n in g["nodes"]:
            n = {k: v for k, v in n.items() if k not in ("updated_at",)}
            n["items"] = [{k: v for k, v in p.items() if k != "id"} for p in n["items"]]
            n["encounters"] = [
                {**e, "enemies": [{k: v for k, v in x.items() if k != "id"} for x in e["enemies"]]}
                for e in n["encounters"]
            ]
            n["choices"] = [
                {
                    **c,
                    "outcomes": [{k: v for k, v in o.items() if k != "id"} for o in c["outcomes"]],
                }
                for c in n["choices"]
            ]
            out.append(n)
        return out

    assert ids_free(after) == ids_free(before)
    used = api.get(f"/series/{sid}/where-used", params={"target_type": "item", "key": "rope"})
    assert sorted(r["role"] for r in used["refs"]) == ["condition", "placement"]


def test_undo_after_entity_deleted_conflicts(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    bid = book["id"]
    rope = api.post(f"/series/{series['id']}/items", {"name": "Rope"})
    start = graph()["nodes"][0]
    api.put(f"/nodes/{start['id']}/items", [{"item_id": rope["id"]}])
    api.patch(f"/nodes/{start['id']}", {"title": "Gate"})
    api.delete(f"/items/{rope['id']}", params={"force": True})
    # Undoing the title edit would restore a placement of the deleted item.
    err = api.post(f"/books/{bid}/undo", expect=409)
    assert "deleted since" in err["detail"]
    assert api.get(f"/nodes/{start['id']}")["title"] == "Gate"  # unchanged


def test_history_is_per_book_and_capped(
    api: Api, series: Json, book: Json, graph: Callable[[], Json], monkeypatch: pytest.MonkeyPatch
) -> None:
    other = api.post(f"/series/{series['id']}/books", {"title": "Other"})
    start = graph()["nodes"][0]
    monkeypatch.setattr(history, "MAX_ENTRIES", 3)
    for i in range(6):
        api.patch(f"/nodes/{start['id']}", {"title": f"T{i}"})
        api.post(f"/nodes/{start['id']}/choices", {"label": f"c{i}"})
    assert state(api, book["id"])["depth"] == 3
    assert not state(api, other["id"])["can_undo"]
    api.get("/books/nope/history", expect=404)


def test_layout_and_act_edits_are_undoable(api: Api, book: Json, graph: Callable[[], Json]) -> None:
    bid = book["id"]
    start = graph()["nodes"][0]
    api.put(
        f"/books/{bid}/layout", {"positions": [{"id": start["id"], "x": 500, "y": 9}]}, expect=204
    )
    assert state(api, bid)["undo_label"] == "Move nodes"
    api.post(f"/books/{bid}/undo", expect=200)
    assert graph()["nodes"][0]["x"] == 0
    act = api.post(f"/books/{bid}/acts", {"title": "Two"})
    api.patch(f"/acts/{act['id']}", {"color": "#123456"})
    api.post(f"/books/{bid}/undo", expect=200)
    api.post(f"/books/{bid}/undo", expect=200)
    assert [a["title"] for a in graph()["acts"]] == ["Act 1"]
    api.patch(f"/books/{bid}", {"title": "Renamed"})
    api.post(f"/books/{bid}/undo", expect=200)
    assert api.get(f"/books/{bid}")["title"] == "The Haunted Bridge"


def test_checkpoints(api: Api, series: Json) -> None:
    cp = api.post("/checkpoints", {"name": "Before big rewrite!"})
    assert cp["name"] == "Before big rewrite"
    api.patch(f"/series/{series['id']}", {"title": "Changed"})
    api.post("/series", {"title": "Extra"})
    safety = api.post(f"/checkpoints/{cp['id']}/restore", expect=200)
    assert safety["name"] == "before restore"
    assert [s["title"] for s in api.get("/series")] == ["The Ashen Cycle"]
    ids = [c["id"] for c in api.get("/checkpoints")]
    assert ids[0] == safety["id"]
    assert cp["id"] in ids
    api.delete(f"/checkpoints/{cp['id']}")
    api.post("/checkpoints/../etc/restore", expect=404)
    api.post("/checkpoints/nope/restore", expect=422)
