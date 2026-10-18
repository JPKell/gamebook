"""Regressions for bugs found in the Phase 1 review (one test per finding)."""

import time
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import select

from gamebook.core import gbx
from gamebook.core.analysis.validation import _coverage
from gamebook.db.models import RefIndex
from gamebook.export import tree
from gamebook.services import refs

from .conftest import Api, Json

ZIP = {"Content-Type": "application/zip"}


def _index(client: TestClient, series_id: str) -> list[tuple[object, ...]]:
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


def _assert_index_fresh(client: TestClient, series_id: str) -> None:
    before = _index(client, series_id)
    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session() as s:
        refs.rebuild_series(s, series_id)
    assert _index(client, series_id) == before


def test_1_node_rename_stays_in_its_book(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    other = api.post(f"/series/{series['id']}/books", {"title": "Two"})
    other_start = api.get(f"/books/{other['id']}/graph")["nodes"][0]
    c = api.post(f"/nodes/{other_start['id']}/choices", {"condition": "visits(start) >= 1"})
    api.patch(f"/nodes/{graph()['nodes'][0]['id']}", {"key": "beginning"})
    assert api.get(f"/nodes/{other_start['id']}")["choices"][0]["condition"] == "visits(start) >= 1"
    del c


def test_2_once_false_survives_round_trip(
    api: Api, series: Json, graph: Callable[[], Json]
) -> None:
    start = graph()["nodes"][0]
    api.post(f"/series/{series['id']}/items", {"name": "Gold Coin"})
    api.patch(
        f"/nodes/{start['id']}", {"on_enter": [{"op": "give", "item": "gold_coin", "once": False}]}
    )
    files = tree.from_zip(api.c.get(f"/api/series/{series['id']}/export.zip").content)
    node_file = next(v for k, v in files.items() if k.endswith("/start.md"))
    assert yaml.safe_load(node_file.split("---\n")[1])["on_enter"][0]["once"] is False
    res = api.c.post(
        "/api/import", content=tree.to_zip(files), headers=ZIP, params={"replace": True}
    )
    assert res.status_code == 201
    assert api.get(f"/nodes/{start['id']}")["on_enter"][0]["once"] is False


def test_3_import_rejects_unsafe_keys_and_lore_types(
    api: Api, series: Json, tmp_path: Path
) -> None:
    api.post(f"/series/{series['id']}/enemies", {"name": "X"})
    api.post(f"/series/{series['id']}/lore", {"name": "Y"})
    files = tree.from_zip(api.c.get(f"/api/series/{series['id']}/export.zip").content)
    evil = dict(files)
    evil["enemies/x.yaml"] = evil["enemies/x.yaml"].replace("key: x", "key: ../../../../escaped")
    res = api.c.post(
        "/api/import", content=tree.to_zip(evil), headers=ZIP, params={"replace": True}
    )
    assert res.status_code == 422
    assert "Invalid key" in res.json()["detail"]

    weird = dict(files)
    weird["lore/weird/y.md"] = weird.pop("lore/other/y.md")
    res = api.c.post(
        "/api/import", content=tree.to_zip(weird), headers=ZIP, params={"replace": True}
    )
    assert res.status_code == 422

    with pytest.raises(tree.TreeError, match="outside"):
        tree.write_tree({"../escape.yaml": "x"}, tmp_path / "out")
    (tmp_path / "real").mkdir()
    (tmp_path / "out2").mkdir()
    (tmp_path / "out2" / "books").symlink_to(tmp_path / "real")
    with pytest.raises(tree.TreeError, match="symlink"):
        tree.write_tree({}, tmp_path / "out2")


def test_4_enemy_linked_to_book_lore_reimports(api: Api, series: Json, book: Json) -> None:
    lore = api.post(f"/series/{series['id']}/lore", {"name": "Bridge", "book_id": book["id"]})
    api.post(
        f"/series/{series['id']}/enemies",
        {"name": "Troll", "book_id": book["id"], "lore_entry_id": lore["id"]},
    )
    files = tree.from_zip(api.c.get(f"/api/series/{series['id']}/export.zip").content)
    res = api.c.post(
        "/api/import", content=tree.to_zip(files), headers=ZIP, params={"replace": True}
    )
    assert res.status_code == 201, res.text


def test_5_enemy_lore_link_validated_and_indexed(api: Api, series: Json, book: Json) -> None:
    sid = series["id"]
    api.post(f"/series/{sid}/enemies", {"name": "A", "lore_entry_id": "nope"}, expect=422)
    other = api.post("/series", {"title": "Other"})
    foreign = api.post(f"/series/{other['id']}/lore", {"name": "Far"})
    api.post(f"/series/{sid}/enemies", {"name": "B", "lore_entry_id": foreign["id"]}, expect=422)
    book_lore = api.post(f"/series/{sid}/lore", {"name": "Local", "book_id": book["id"]})
    api.post(f"/series/{sid}/enemies", {"name": "C", "lore_entry_id": book_lore["id"]}, expect=422)
    shared = api.post(f"/series/{sid}/lore", {"name": "Shared"})
    api.post(f"/series/{sid}/enemies", {"name": "D", "lore_entry_id": shared["id"]})
    api.delete(f"/lore/{shared['id']}", expect=409)  # the link counts as a use


def test_6_nullable_fields_can_be_cleared(api: Api, series: Json) -> None:
    item = api.post(
        f"/series/{series['id']}/items", {"name": "Rope", "slot": "belt", "max_stack": 3, "uses": 2}
    )
    cleared = api.patch(f"/items/{item['id']}", {"slot": None, "max_stack": None, "uses": None})
    assert (cleared["slot"], cleared["max_stack"], cleared["uses"]) == (None, None, None)
    # Non-nullable fields treat null as "unchanged".
    assert api.patch(f"/items/{item['id']}", {"description": None})["description"] == ""


def test_7_book_scoped_entities_stay_in_their_book(
    client: TestClient, api: Api, series: Json, book: Json
) -> None:
    sid = series["id"]
    other = api.post(f"/series/{sid}/books", {"title": "Two"})
    mine = api.post(f"/series/{sid}/items", {"name": "Token", "book_id": book["id"]})
    other_start = api.get(f"/books/{other['id']}/graph")["nodes"][0]
    api.put(f"/nodes/{other_start['id']}/items", [{"item_id": mine["id"]}], expect=422)
    api.put(f"/nodes/{other_start['id']}/shop", {"items": [{"item_id": mine["id"]}]}, expect=422)
    shared = api.post(f"/series/{sid}/items", {"name": "Coin"})
    api.put(f"/nodes/{other_start['id']}/items", [{"item_id": shared["id"]}])
    api.post(f"/nodes/{other_start['id']}/choices", {"condition": "has(token)"})
    api.delete(f"/books/{book['id']}")
    _assert_index_fresh(client, sid)


def test_8_huge_roll_ranges_are_fast() -> None:
    start = time.perf_counter()
    gaps, overlaps = _coverage((1, 10**12), [(1, 10, "a"), (5, 10**12, "b")])
    assert time.perf_counter() - start < 0.1
    assert gaps == []
    assert overlaps == [(5, 10)]
    assert _coverage((2, 12), [(2, 5, "a"), (7, 13, "b"), (12, 12, "c")]) == ([(6, 6)], [(12, 12)])


def test_9_distribution_is_bounded() -> None:
    start = time.perf_counter()
    assert gbx.distribution(gbx.parse("8d1000")) is None
    d = gbx.distribution(gbx.parse("10d6"))
    assert d is not None
    assert sum(d.values()) == 1
    assert time.perf_counter() - start < 1


@pytest.mark.parametrize("src", ["-" * 1500 + "1", "not " * 300 + "true", "+".join(["1"] * 900)])
def test_10_deep_expressions_are_syntax_errors(api: Api, series: Json, src: str) -> None:
    with pytest.raises(gbx.GbxSyntaxError, match="nested too deeply"):
        gbx.parse(src[:2000])
    res = api.post(
        "/gbx/check",
        {"source": src[:2000], "context": "condition", "series_id": series["id"]},
        expect=200,
    )
    assert res["ok"] is False


@pytest.mark.parametrize(
    ("src", "english"),
    [("true", "always"), ("false", "never"), ("not true", "never"), ("not false", "always")],
)
def test_11_boolean_literals_in_english(src: str, english: str) -> None:
    assert gbx.condition_to_english(gbx.parse(src)) == english


def test_12_index_fresh_after_node_create_rename_and_rules_change(
    client: TestClient, api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    sid = series["id"]
    start = graph()["nodes"][0]
    api.post(f"/nodes/{start['id']}/choices", {"condition": "visits(hall) > 0 and tier >= medium"})
    api.post(f"/books/{book['id']}/nodes", {"act_id": start["act_id"], "title": "Hall"})
    _assert_index_fresh(client, sid)
    lair = api.post(f"/books/{book['id']}/nodes", {"act_id": start["act_id"], "title": "Lair"})
    api.post(f"/nodes/{start['id']}/variants", {"condition": "visits(den) > 0"})
    api.patch(f"/nodes/{lair['id']}", {"key": "den"})
    _assert_index_fresh(client, sid)

    rs = api.get(f"/series/{sid}/rule-systems")[0]
    definition = rs["definition"]
    definition["tiers"][1]["key"] = "mid"
    definition["tiers"][2]["parent"] = "mid"
    api.patch(f"/rule-systems/{rs['id']}", {"definition": definition})
    _assert_index_fresh(client, sid)


def test_null_key_in_patch_is_ignored(api: Api, series: Json, graph: Callable[[], Json]) -> None:
    start = graph()["nodes"][0]
    api.patch(f"/nodes/{start['id']}", {"key": "entrance"})
    assert api.patch(f"/nodes/{start['id']}", {"key": None, "title": "Gate"})["key"] == "entrance"
    item = api.post(f"/series/{series['id']}/items", {"name": "Rope", "key": "cord_of_ages"})
    assert api.patch(f"/items/{item['id']}", {"key": None, "name": "Cord"})["key"] == "cord_of_ages"


def test_auto_keys_follow_title(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    start = graph()["nodes"][0]
    node = api.post(f"/books/{book['id']}/nodes", {"act_id": start["act_id"]})
    assert node["key"] == "untitled"
    api.post(f"/nodes/{start['id']}/variants", {"condition": "visits(untitled) > 0"})
    renamed = api.patch(f"/nodes/{node['id']}", {"title": "The Bridge"})
    assert renamed["key"] == "the_bridge"
    # References follow the key.
    assert api.get(f"/nodes/{start['id']}")["variants"][1]["condition"] == "visits(the_bridge) > 0"
    # Suffixed auto keys follow too; an explicit key in the same request wins.
    second = api.post(
        f"/books/{book['id']}/nodes", {"act_id": start["act_id"], "title": "The Bridge"}
    )
    assert second["key"] == "the_bridge_2"
    assert api.patch(f"/nodes/{second['id']}", {"title": "Ford"})["key"] == "ford"
    assert (
        api.patch(f"/nodes/{second['id']}", {"title": "Weir", "key": "my_weir"})["key"] == "my_weir"
    )
    item = api.post(f"/series/{series['id']}/items", {"name": "Rope"})
    assert api.patch(f"/items/{item['id']}", {"name": "Silk Rope"})["key"] == "silk_rope"


def test_malformed_import_is_422_not_500(api: Api, series: Json, book: Json) -> None:
    files = tree.from_zip(api.c.get(f"/api/series/{series['id']}/export.zip").content)
    book_yaml = next(k for k in files if k.endswith("book.yaml"))
    files[book_yaml] = "id: x\n"  # missing required fields
    res = api.c.post(
        "/api/import", content=tree.to_zip(files), headers=ZIP, params={"replace": True}
    )
    assert res.status_code == 422
    assert res.json()["code"] == "invalid"
    files[book_yaml] = "id: x\nkey: two\n"  # key fine, title missing → KeyError inside
    res = api.c.post(
        "/api/import", content=tree.to_zip(files), headers=ZIP, params={"replace": True}
    )
    assert res.status_code == 422
    assert "Malformed export" in res.json()["detail"]
