"""Enemy level tables, series entity problems and enriched where-used."""

from collections.abc import Callable

from .conftest import Api, Json

ORC = {"SKILL": "5 + level", "STAMINA": "4 + level * 2", "ARMOR": "floor(level / 2)"}


def test_enemy_levels_per_tier(api: Api, series: Json) -> None:
    orc = api.post(f"/series/{series['id']}/enemies", {"name": "Orc", "stat_formulas": ORC})
    res = api.get(f"/enemies/{orc['id']}/levels", params={"level_from": 1, "level_to": 5})
    tiers = {t["key"]: t for t in res["tiers"]}
    assert list(tiers) == ["basic", "medium", "advanced"]
    assert tiers["basic"]["stats"] == ["SKILL", "STAMINA"]
    assert tiers["medium"]["stats"] == ["ARMOR", "SKILL", "STAMINA"]
    assert tiers["basic"]["rows"][0] == {"level": 1, "stats": {"SKILL": 6, "STAMINA": 6}}
    assert tiers["medium"]["rows"][3] == {
        "level": 4,
        "stats": {"ARMOR": 2, "SKILL": 9, "STAMINA": 12},
    }
    assert res["errors"] == {}
    assert all(t["missing"] == [] for t in res["tiers"])


def test_enemy_levels_report_missing_and_broken_formulas(api: Api, series: Json) -> None:
    rat = api.post(
        f"/series/{series['id']}/enemies",
        {"name": "Rat", "stat_formulas": {"SKILL": "2 +", "STAMINA": "1d6"}},
    )
    res = api.get(f"/enemies/{rat['id']}/levels")
    medium = next(t for t in res["tiers"] if t["key"] == "medium")
    assert medium["missing"] == ["ARMOR"]
    assert medium["rows"][0]["stats"]["SKILL"] == 0  # unparseable counts as 0
    assert "SKILL" in res["errors"]
    assert "dice" in res["errors"]["STAMINA"].lower()
    api.get(f"/enemies/{rat['id']}/levels", params={"level_from": 5, "level_to": 2}, expect=422)
    api.get(f"/enemies/{rat['id']}/levels", params={"level_from": 1, "level_to": 100}, expect=422)
    api.get("/enemies/nope/levels", expect=404)


def test_series_entity_problems(api: Api, series: Json, book: Json) -> None:
    sid = series["id"]
    assert api.get(f"/series/{sid}/entity-problems")["counts"] == {
        "errors": 0,
        "warnings": 0,
        "info": 0,
    }
    api.post(
        f"/series/{sid}/enemies",
        {"name": "Ghost", "stat_formulas": {"SKILL": "3"}, "book_id": book["id"]},
    )
    api.post(
        f"/series/{sid}/tables",
        {"name": "Den", "dice": "1d6", "entries": [{"lo": 1, "hi": 3, "kind": "nothing"}]},
    )
    api.post(
        f"/series/{sid}/items", {"name": "Charm", "modifiers": [{"stat": "MAGIC", "amount": "1"}]}
    )
    res = api.get(f"/series/{sid}/entity-problems")
    codes = {(p["entity_type"], p["code"]) for p in res["problems"]}
    assert ("enemy", "enemy_missing_stat") in codes  # book-scoped enemies are checked too
    assert ("table", "table_gap") in codes
    assert ("item", "unknown_stat") in codes
    assert all(p["entity_type"] in {"enemy", "item", "table"} for p in res["problems"])
    api.get("/series/nope/entity-problems", expect=404)


def test_where_used_names_books_and_sources(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    sid = series["id"]
    api.post(f"/series/{sid}/items", {"name": "Potion"})
    api.post(f"/series/{sid}/enemies", {"name": "Orc", "loot": [{"item": "potion", "qty": 2}]})
    api.post(
        f"/series/{sid}/tables",
        {
            "name": "Den",
            "dice": "1d6",
            "entries": [{"lo": 1, "hi": 6, "kind": "item", "item": "potion"}],
        },
    )
    start = graph()["nodes"][0]
    api.patch(f"/nodes/{start['id']}", {"on_enter": [{"op": "give", "item": "potion", "qty": 3}]})
    used = api.get(f"/series/{sid}/where-used", params={"target_type": "item", "key": "potion"})
    by_role = {r["role"]: r for r in used["refs"]}
    assert by_role["effect.give"]["book_title"] == "The Haunted Bridge"
    assert by_role["effect.give"]["node_title"] == "Start"
    assert by_role["loot"]["source_label"] == "Orc"
    assert by_role["table"]["source_label"] == "Den"
    assert used["total_qty"] == 3 + 2 + 1


def test_item_totals(api: Api, series: Json, graph: Callable[[], Json]) -> None:
    sid = series["id"]
    potion = api.post(f"/series/{sid}/items", {"name": "Potion"})
    api.post(f"/series/{sid}/items", {"name": "Unused"})
    start = graph()["nodes"][0]
    api.put(f"/nodes/{start['id']}/items", [{"item_id": potion["id"], "qty": 2}])
    api.post(f"/nodes/{start['id']}/choices", {"condition": "has(potion)"})
    totals = api.get(f"/series/{sid}/item-totals")
    assert totals == {"potion": {"total": 2, "uses": 2, "unlimited": False}}


def test_item_totals_shop_stock(api: Api, series: Json, graph: Callable[[], Json]) -> None:
    """Shop stock 0 supplies nothing; unlimited stock is flagged, not counted as 1."""
    sid = series["id"]
    rope = api.post(f"/series/{sid}/items", {"name": "Rope"})
    gem = api.post(f"/series/{sid}/items", {"name": "Gem"})
    start = graph()["nodes"][0]
    api.put(
        f"/nodes/{start['id']}/shop",
        {
            "is_shop": True,
            "items": [
                {"item_id": rope["id"], "price": 1, "stock": None},
                {"item_id": gem["id"], "price": 5, "stock": 0},
            ],
        },
    )
    totals = api.get(f"/series/{sid}/item-totals")
    assert totals["rope"] == {"total": 0, "uses": 1, "unlimited": True}
    assert totals["gem"] == {"total": 0, "uses": 1, "unlimited": False}
    used = api.get(f"/series/{sid}/where-used?target_type=item&key=rope")
    assert used["total_qty"] == 0
    assert used["unlimited"] is True


def test_enemy_levels_treat_blank_formula_as_missing(api: Api, series: Json) -> None:
    sid = series["id"]
    enemy = api.post(f"/series/{sid}/enemies", {"name": "Wisp", "stat_formulas": {"SKILL": " "}})
    out = api.get(f"/enemies/{enemy['id']}/levels")
    assert "SKILL" in out["tiers"][0]["missing"]
