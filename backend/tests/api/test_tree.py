"""Git tree export/import: deterministic, lossless round trips."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from gamebook.api import create_app
from gamebook.cli import main as cli
from gamebook.config import Settings
from gamebook.export import tree

from .conftest import Api, Json


def build_rich_series(api: Api) -> Json:
    """A series exercising every exported field."""
    s = api.post(
        "/series",
        {
            "title": "The Ashen Cycle",
            "description": "Ash.\nAlways ash.",
            "style": {"tense": "past", "word_max": 300},
        },
    )
    sid = s["id"]
    b = api.post(
        f"/series/{sid}/books", {"title": "The Haunted Bridge", "synopsis": "A bridge.\nHaunted."}
    )
    b2 = api.post(f"/series/{sid}/books", {"title": "The Drowned King"})
    api.patch(f"/books/{b['id']}", {"style_overrides": {"voice": "wry"}})

    crypt = api.post(
        f"/series/{sid}/lore",
        {
            "name": "The Crypt",
            "type": "location",
            "body": "Cold stone.\n\nDripping.",
            "fields": {"climate": "damp"},
        },
    )
    api.post(f"/series/{sid}/lore", {"name": "Bridge Lore", "type": "history", "book_id": b["id"]})
    mara = api.post(
        f"/series/{sid}/characters",
        {"name": "Mara", "role": "guide", "notes": "Knows the river.", "relationships": []},
    )
    api.post(
        f"/series/{sid}/characters",
        {"name": "Tomas", "relationships": [{"character": "mara", "kind": "sibling"}]},
    )
    rope = api.post(
        f"/series/{sid}/items",
        {
            "name": "Rope",
            "category": "equipment",
            "slot": "belt",
            "value": 2,
            "modifiers": [{"stat": "SKILL", "amount": "1", "min_tier": "medium"}],
        },
    )
    potion = api.post(
        f"/series/{sid}/items",
        {
            "name": "Potion",
            "category": "consumable",
            "stackable": True,
            "max_stack": 5,
            "uses": 1,
            "use_effects": [{"op": "modify", "stat": "STAMINA", "amount": "4"}],
        },
    )
    api.post(
        f"/series/{sid}/items", {"name": "Bridge Token", "category": "key", "book_id": b["id"]}
    )
    orc = api.post(
        f"/series/{sid}/enemies",
        {
            "name": "Orc",
            "tags": ["brute"],
            "default_level": 2,
            "stat_formulas": {
                "SKILL": "6 + level",
                "STAMINA": "5 + level * 2",
                "ARMOR": "floor(level / 2)",
            },
            "loot": [{"item": "potion", "qty": 2}],
            "lore_entry_id": crypt["id"],
        },
    )
    table = api.post(
        f"/series/{sid}/tables",
        {
            "name": "Wandering",
            "dice": "1d6",
            "entries": [
                {"lo": 1, "hi": 4, "kind": "enemies", "enemies": [{"enemy": "orc", "level": 2}]},
                {"lo": 5, "hi": 6, "kind": "gold", "amount": "1d6"},
            ],
        },
    )

    g = api.get(f"/books/{b['id']}/graph")
    act1, start = g["acts"][0], g["nodes"][0]
    api.patch(f"/acts/{act1['id']}", {"color": "#aa3355", "summary": "Arrival."})
    act2 = api.post(f"/books/{b['id']}/acts", {"title": "The Depths"})
    api.patch(
        f"/nodes/{start['id']}",
        {
            "is_act_exit": True,
            "beat_notes": "You arrive.\n\nMist everywhere.",
            "location_id": crypt["id"],
            "character_ids": [mara["id"]],
            "on_enter": [
                {"op": "give", "item": "rope"},
                {"op": "set_flag", "flag": "ARRIVED", "once": True},
            ],
            "section_pin": 1,
            "x": 10.5,
            "y": -3,
        },
    )
    api.put(f"/nodes/{start['id']}/items", [{"item_id": potion["id"], "qty": 2}])
    hall = api.post(
        f"/books/{b['id']}/nodes",
        {
            "act_id": act2["id"],
            "title": "Hall",
            "link_from": {"node_id": start["id"], "label": "Descend"},
        },
    )
    api.patch(
        f"/nodes/{hall['id']}",
        {"is_act_entry": True, "canonical_predecessor_id": start["id"], "collapsed": True},
    )
    enc = api.post(
        f"/nodes/{hall['id']}/encounters",
        {
            "label": "Orcs",
            "fight": "simultaneous",
            "enemies": [{"enemy_id": orc["id"], "level": 3, "count": 2}],
        },
    )
    api.post(
        f"/nodes/{hall['id']}/encounters",
        {"label": "Random", "mode": "table", "table_id": table["id"]},
    )
    win = api.post(f"/books/{b['id']}/nodes", {"act_id": act2["id"], "title": "Victory"})
    api.patch(
        f"/nodes/{win['id']}",
        {"ending_kind": "victory", "ending_grade": "secret", "ending_label": "The True Path"},
    )
    dead = api.post(f"/books/{b['id']}/nodes", {"act_id": act2["id"], "title": "Dead"})
    api.patch(f"/nodes/{dead['id']}", {"ending_kind": "death"})
    api.post(
        f"/nodes/{hall['id']}/choices",
        {
            "label": "Fight",
            "kind": "combat",
            "encounter_id": enc["id"],
            "flee_allowed": True,
            "outcomes": [
                {"key": "win", "target_node_id": win["id"]},
                {"key": "lose", "target_node_id": dead["id"]},
                {"key": "flee", "target_node_id": start["id"]},
            ],
        },
    )
    api.post(
        f"/nodes/{hall['id']}/choices",
        {
            "label": "Gamble",
            "kind": "roll",
            "dice": "2d6",
            "outcomes": [
                {"key": "low", "target_node_id": dead["id"], "range_lo": 2, "range_hi": 6},
                {"key": "high", "target_node_id": win["id"], "range_lo": 7, "range_hi": 12},
            ],
        },
    )
    api.post(
        f"/nodes/{hall['id']}/choices",
        {
            "label": "Sneak",
            "condition": "skill(STEALTH)",
            "min_tier": "advanced",
            "unmet_display": "show_disabled",
            "print_text": "If you are stealthy, turn to",
            "effects": [{"op": "modify", "stat": "LUCK", "amount": "-1"}],
            "target_node_id": win["id"],
        },
    )
    api.post(
        f"/nodes/{hall['id']}/variants",
        {"label": "Return", "condition": "visits(hall) > 1", "priority": 2},
    )
    shop = api.post(f"/books/{b['id']}/nodes", {"act_id": act1["id"], "title": "Empty Stall"})
    api.put(f"/nodes/{shop['id']}/shop", {"items": []})
    market = api.post(f"/books/{b['id']}/nodes", {"act_id": act1["id"], "title": "Market"})
    api.put(
        f"/nodes/{market['id']}/shop",
        {
            "sell_rate": 50,
            "items": [
                {"item_id": rope["id"], "price": 3, "stock": 2},
                {"item_id": potion["id"], "price": 5},
            ],
        },
    )
    api.post(f"/series/{sid}/rule-systems", {"name": "Experimental"})
    api.post(
        f"/acts/{act1['id']}/beats",
        {
            "title": "Arrival",
            "description": "Meet [[mara]] in the mist.",
            "node_ids": [start["id"]],
        },
    )
    api.post(f"/acts/{act2['id']}/beats", {"title": "Unwritten"})
    start_variant = api.get(f"/books/{b['id']}/graph")["nodes"][0]["variants"][0]["id"]
    api.post(
        f"/variants/{start_variant}/prose",
        {"text": "Mist curls around you.\n\nSomewhere, a bell.", "approve": True},
    )
    del b2
    result: Json = s
    return result


@pytest.fixture
def fresh_client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(data_dir=tmp_path / "fresh"))) as c:
        yield c


def _export(api: Api, series_id: str) -> dict[str, str]:
    res = api.c.get(f"/api/series/{series_id}/export.zip")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    return tree.from_zip(res.content)


def _normalise_graph(g: Json) -> Any:
    """Graph without timestamps and the ids of unreferenced child rows
    (outcomes, placements, shop entries, encounter enemies), which are regenerated."""

    def scrub(x: Any) -> Any:
        if isinstance(x, dict):
            child_row = any(k in x for k in ("range_lo", "item_id", "enemy_id"))
            return {
                k: scrub(v)
                for k, v in x.items()
                if k not in ("created_at", "updated_at") and not (k == "id" and child_row)
            }
        if isinstance(x, list):
            return [scrub(v) for v in x]
        return x

    return scrub(g)


def test_round_trip_is_lossless_and_deterministic(api: Api, fresh_client: TestClient) -> None:
    s = build_rich_series(api)
    files = _export(api, s["id"])
    assert files == _export(api, s["id"])  # deterministic

    fresh = Api(fresh_client)
    imported = fresh_client.post(
        "/api/import", content=tree.to_zip(files), headers={"Content-Type": "application/zip"}
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["id"] == s["id"]
    assert _export(fresh, s["id"]) == files

    for book in api.get(f"/series/{s['id']}/books"):
        original = _normalise_graph(api.get(f"/books/{book['id']}/graph"))
        copied = _normalise_graph(fresh.get(f"/books/{book['id']}/graph"))
        assert copied == original
        assert fresh.get(f"/books/{book['id']}/problems") == api.get(
            f"/books/{book['id']}/problems"
        )
        assert fresh.get(f"/books/{book['id']}/outline") == api.get(f"/books/{book['id']}/outline")

        def queue(a: Api, book_id: str = book["id"]) -> Any:
            q = a.get(f"/books/{book_id}/writing-queue")
            # Imported prose versions get fresh ids; everything else must match.
            return q["counts"], [{**r, "latest_id": None} for r in q["rows"]]

        assert queue(fresh) == queue(api)

    def strip(rows: list[Json]) -> list[Json]:
        return [{k: v for k, v in r.items() if k != "updated_at"} for r in rows]

    for plural in ("items", "enemies", "tables", "characters", "lore", "rule-systems"):
        assert strip(fresh.get(f"/series/{s['id']}/{plural}")) == strip(
            api.get(f"/series/{s['id']}/{plural}")
        )
    assert fresh.get(f"/series/{s['id']}/flags") == api.get(f"/series/{s['id']}/flags")


def test_tree_layout_is_human_friendly(api: Api) -> None:
    s = build_rich_series(api)
    files = _export(api, s["id"])
    assert "series.yaml" in files
    assert "rules/standard.yaml" in files
    assert "items/rope.yaml" in files
    assert "books/01-the_haunted_bridge/items/bridge_token.yaml" in files
    assert "lore/location/the_crypt.md" in files
    assert "books/01-the_haunted_bridge/lore/history/bridge_lore.md" in files
    node = files["books/01-the_haunted_bridge/acts/01-act_1/nodes/start.md"]
    assert node.startswith("---\n")
    assert node.endswith("---\nYou arrive.\n\nMist everywhere.\n")
    meta = yaml.safe_load(node.split("---\n")[1])
    assert meta["characters"] == ["mara"]
    assert meta["location"] == "the_crypt"
    assert meta["items"] == [{"item": "potion", "qty": 2}]
    assert "created_at" not in node
    hall = yaml.safe_load(
        files["books/01-the_haunted_bridge/acts/02-the_depths/nodes/hall.md"].split("---\n")[1]
    )
    assert hall["choices"][1]["outcomes"][0] == {"key": "low", "target": "dead", "range": [2, 6]}
    assert yaml.safe_load(
        files["books/01-the_haunted_bridge/acts/01-act_1/nodes/empty_stall.md"].split("---\n")[1]
    )["shop"] == {"enabled": True}
    lore = files["lore/location/the_crypt.md"]
    assert "Cold stone.\n\nDripping." in lore


def test_import_conflicts_and_errors(api: Api) -> None:
    s = build_rich_series(api)
    data = tree.to_zip(_export(api, s["id"]))
    headers = {"Content-Type": "application/zip"}
    res = api.c.post("/api/import", content=data, headers=headers)
    assert res.status_code == 409
    res = api.c.post("/api/import", content=data, headers=headers, params={"replace": True})
    assert res.status_code == 201
    assert len(api.get("/series")) == 1

    assert api.c.post("/api/import", content=b"not a zip", headers=headers).status_code == 422
    assert (
        api.c.post(
            "/api/import", content=tree.to_zip({"x.yaml": "a: 1"}), headers=headers
        ).status_code
        == 422
    )
    broken = _export(api, s["id"])
    path = "books/01-the_haunted_bridge/acts/01-act_1/nodes/start.md"
    broken[path] = broken[path].replace("location: the_crypt", "location: nowhere")
    res = api.c.post(
        "/api/import", content=tree.to_zip(broken), headers=headers, params={"replace": True}
    )
    assert res.status_code == 422
    assert "unknown key 'nowhere'" in res.json()["detail"]
    # The failed import rolled back: the series is still intact.
    assert api.get(f"/series/{s['id']}")["title"] == "The Ashen Cycle"


def test_cli_export_import(
    api: Api, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = build_rich_series(api)
    monkeypatch.setenv("GAMEBOOK_DATABASE_URL", settings.database_url)
    from gamebook.config import get_settings

    get_settings.cache_clear()
    out = tmp_path / "repo"
    out.mkdir()
    (out / "README.md").write_text("mine")
    (out / "books").mkdir()
    (out / "books" / "stale.md").write_text("old")
    try:
        cli(["export", s["key"], str(out)])
        assert (out / "README.md").read_text() == "mine"  # untouched
        assert not (out / "books" / "stale.md").exists()  # stale managed file removed
        files = tree.read_tree(out)
        assert files == _export(api, s["id"])

        monkeypatch.setenv("GAMEBOOK_DATABASE_URL", f"sqlite:///{tmp_path / 'other.db'}")
        get_settings.cache_clear()
        cli(["import", str(out)])
        with pytest.raises(Exception, match="already exists"):
            cli(["import", str(out)])
        cli(["import", str(out), "--replace"])
    finally:
        get_settings.cache_clear()
