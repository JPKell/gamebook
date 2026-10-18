"""End-to-end authoring flows through the HTTP API."""

from collections.abc import Callable
from typing import Any

from .conftest import Api, Json


def node_by_key(g: Json, key: str) -> Json:
    return next(n for n in g["nodes"] if n["key"] == key)


# ── series & books ───────────────────────────────────────────────────────


def test_series_crud_and_default_rules(api: Api) -> None:
    s = api.post("/series", {"title": "The Ashen Cycle", "description": "Grey skies"})
    assert s["key"] == "the_ashen_cycle"
    assert s["style"]["pov"] == "second"
    assert s["books"] == []

    systems = api.get(f"/series/{s['id']}/rule-systems")
    assert len(systems) == 1
    assert systems[0]["is_active"]
    assert [t["key"] for t in systems[0]["definition"]["tiers"]] == ["basic", "medium", "advanced"]

    api.patch(f"/series/{s['id']}", {"title": "Ash", "style": {"tense": "past"}})
    got = api.get(f"/series/{s['id']}")
    assert (got["title"], got["style"]["tense"]) == ("Ash", "past")

    dup = api.post("/series", {"title": "X", "key": "the_ashen_cycle"}, expect=409)
    assert dup["code"] == "conflict"
    api.post("/series", {"title": "X", "key": "bad key"}, expect=422)

    api.delete(f"/series/{s['id']}")
    api.get(f"/series/{s['id']}", expect=404)


def test_new_book_is_playable_skeleton(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    assert book["number"] == 1
    g = graph()
    assert [a["title"] for a in g["acts"]] == ["Act 1"]
    assert [n["key"] for n in g["nodes"]] == ["start"]
    assert g["book"]["start_node_id"] == g["nodes"][0]["id"]
    assert g["nodes"][0]["variants"][0]["label"] == "Default"

    second = api.post(f"/series/{series['id']}/books", {"title": "Book Two"})
    assert second["number"] == 2
    assert [b["title"] for b in api.get(f"/series/{series['id']}/books")] == [
        "The Haunted Bridge",
        "Book Two",
    ]


def test_delete_series_with_content(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    start = graph()["nodes"][0]
    api.post(
        f"/books/{book['id']}/nodes",
        {"act_id": start["act_id"], "link_from": {"node_id": start["id"]}},
    )
    api.delete(f"/series/{series['id']}")
    api.get(f"/books/{book['id']}", expect=404)


# ── nodes & choices ──────────────────────────────────────────────────────


def test_create_linked_node_and_edit(api: Api, book: Json, graph: Callable[[], Json]) -> None:
    start = graph()["nodes"][0]
    bridge = api.post(
        f"/books/{book['id']}/nodes",
        {
            "act_id": start["act_id"],
            "title": "The Haunted Bridge",
            "x": 200,
            "link_from": {"node_id": start["id"], "label": "Cross"},
        },
    )
    assert bridge["key"] == "the_haunted_bridge"
    start = node_by_key(graph(), "start")
    assert start["choices"][0]["label"] == "Cross"
    assert start["choices"][0]["outcomes"][0]["target_node_id"] == bridge["id"]

    updated = api.patch(
        f"/nodes/{bridge['id']}",
        {
            "beat_notes": "A ghost blocks the way.",
            "ending_kind": "victory",
            "ending_grade": "good",
            "on_enter": [{"op": "give", "item": "rope"}, {"op": "set_flag", "flag": "BRIDGE"}],
        },
    )
    assert updated["ending_kind"] == "victory"
    assert updated["on_enter"][0] == {
        "op": "give",
        "item": "rope",
        "qty": 1,
        "once": None,
        "min_tier": None,
        "print_text": None,
    }

    cleared = api.patch(f"/nodes/{bridge['id']}", {"ending_kind": None})
    assert cleared["ending_kind"] is None
    assert cleared["ending_grade"] is None

    api.patch(f"/nodes/{bridge['id']}", {"on_enter": [{"op": "explode"}]}, expect=422)


def test_choice_kinds_and_outcomes(api: Api, book: Json, graph: Callable[[], Json]) -> None:
    start = graph()["nodes"][0]
    nid = start["id"]

    roll = api.post(f"/nodes/{nid}/choices", {"label": "Roll", "kind": "roll"})
    assert roll["dice"] == "2d6"
    assert [(o["key"], o["range_lo"], o["range_hi"]) for o in roll["outcomes"]] == [
        ("low", 2, 6),
        ("high", 7, 12),
    ]

    test = api.post(f"/nodes/{nid}/choices", {"label": "Luck", "kind": "test", "test": "luck"})
    assert [o["key"] for o in test["outcomes"]] == ["success", "failure"]

    combat = api.post(f"/nodes/{nid}/choices", {"label": "Fight", "kind": "combat"})
    assert [o["key"] for o in combat["outcomes"]] == ["win", "lose"]
    combat = api.patch(f"/choices/{combat['id']}", {"flee_allowed": True})
    assert [o["key"] for o in combat["outcomes"]] == ["win", "lose", "flee"]

    # Changing kind keeps destinations for shared keys.
    other = api.post(f"/books/{book['id']}/nodes", {"act_id": start["act_id"]})
    goto = api.post(f"/nodes/{nid}/choices", {"label": "Go", "target_node_id": other["id"]})
    as_test = api.patch(f"/choices/{goto['id']}", {"kind": "test"})
    assert [o["target_node_id"] for o in as_test["outcomes"]] == [None, None]
    back = api.patch(f"/choices/{goto['id']}", {"kind": "goto", "target_node_id": other["id"]})
    assert back["outcomes"][0]["target_node_id"] == other["id"]

    order = [c["id"] for c in reversed(node_by_key(graph(), "start")["choices"])]
    reordered = api.put(f"/nodes/{nid}/choices/order", {"ids": order})
    assert [c["id"] for c in reordered] == order
    api.put(f"/nodes/{nid}/choices/order", {"ids": order[:1]}, expect=422)

    api.delete(f"/choices/{roll['id']}")
    assert len(node_by_key(graph(), "start")["choices"]) == 3


def test_cross_book_links_rejected(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    other_book = api.post(f"/series/{series['id']}/books", {"title": "Other"})
    other_start = api.get(f"/books/{other_book['id']}/graph")["nodes"][0]
    start = graph()["nodes"][0]
    err = api.post(
        f"/nodes/{start['id']}/choices", {"target_node_id": other_start["id"]}, expect=422
    )
    assert err["details"]["field"] == "outcomes"
    api.patch(f"/nodes/{start['id']}", {"act_id": other_start["act_id"]}, expect=422)
    api.post(f"/books/{book['id']}/nodes", {"act_id": other_start["act_id"]}, expect=422)


def test_delete_node_clears_incoming_targets(
    api: Api, book: Json, graph: Callable[[], Json]
) -> None:
    start = graph()["nodes"][0]
    target = api.post(
        f"/books/{book['id']}/nodes",
        {"act_id": start["act_id"], "link_from": {"node_id": start["id"]}},
    )
    api.delete(f"/nodes/{target['id']}")
    choice = node_by_key(graph(), "start")["choices"][0]
    assert choice["outcomes"][0]["target_node_id"] is None
    # The start node itself can be deleted; the book loses its start.
    api.delete(f"/nodes/{start['id']}")
    assert graph()["book"]["start_node_id"] is None


def test_variants(api: Api, graph: Callable[[], Json]) -> None:
    nid = graph()["nodes"][0]["id"]
    v = api.post(
        f"/nodes/{nid}/variants",
        {"label": "Returning", "condition": "visits(start) > 1", "priority": 1},
    )
    api.patch(f"/variants/{v['id']}", {"condition": ""})
    assert node_by_key(graph(), "start")["variants"][1]["condition"] is None
    api.delete(f"/variants/{v['id']}")
    assert len(node_by_key(graph(), "start")["variants"]) == 1


def test_layout_and_duplicate(api: Api, book: Json, graph: Callable[[], Json]) -> None:
    start = graph()["nodes"][0]
    b = api.post(
        f"/books/{book['id']}/nodes",
        {"act_id": start["act_id"], "title": "B", "link_from": {"node_id": start["id"]}},
    )
    api.post(f"/nodes/{b['id']}/choices", {"label": "Back", "target_node_id": start["id"]})

    api.put(
        f"/books/{book['id']}/layout",
        {"positions": [{"id": b["id"], "x": 10, "y": 20}]},
        expect=204,
    )
    assert (node_by_key(graph(), "b")["x"], node_by_key(graph(), "b")["y"]) == (10, 20)
    api.put(
        f"/books/{book['id']}/layout", {"positions": [{"id": "nope", "x": 0, "y": 0}]}, expect=422
    )

    mapping = api.post(
        f"/books/{book['id']}/duplicate", {"node_ids": [start["id"], b["id"]]}, expect=200
    )["mapping"]
    g = graph()
    start_copy = next(n for n in g["nodes"] if n["id"] == mapping[start["id"]])
    b_copy = next(n for n in g["nodes"] if n["id"] == mapping[b["id"]])
    assert start_copy["key"] == "start_copy"
    # Links inside the copied set point at the copies; the book start is unchanged.
    assert start_copy["choices"][0]["outcomes"][0]["target_node_id"] == b_copy["id"]
    assert b_copy["choices"][0]["outcomes"][0]["target_node_id"] == start_copy["id"]
    assert g["book"]["start_node_id"] == start["id"]


def test_acts(api: Api, book: Json, graph: Callable[[], Json]) -> None:
    act1 = graph()["acts"][0]
    act2 = api.post(f"/books/{book['id']}/acts", {"title": "Act 2 — The Descent"})
    assert (act2["key"], act2["position"]) == ("act_2_the_descent", 1)
    n = api.post(f"/books/{book['id']}/nodes", {"act_id": act2["id"]})

    order = api.put(f"/books/{book['id']}/acts/order", {"ids": [act2["id"], act1["id"]]})
    assert [a["id"] for a in order] == [act2["id"], act1["id"]]

    err = api.delete(f"/acts/{act2['id']}", expect=409)
    assert err["details"]["node_count"] == 1
    api.delete(f"/acts/{act2['id']}", params={"force": True})
    api.get(f"/nodes/{n['id']}", expect=404)
    assert [a["position"] for a in graph()["acts"]] == [0]


# ── entities & references ────────────────────────────────────────────────


def test_entity_crud_scopes_and_where_used(
    api: Api, series: Json, book: Json, graph: Callable[[], Json]
) -> None:
    sid = series["id"]
    rope = api.post(f"/series/{sid}/items", {"name": "Rope", "category": "equipment"})
    lamp = api.post(f"/series/{sid}/items", {"name": "Lamp", "book_id": book["id"]})
    other_book = api.post(f"/series/{sid}/books", {"title": "Other"})
    api.post(f"/series/{sid}/items", {"name": "Compass", "book_id": other_book["id"]})

    assert {i["key"] for i in api.get(f"/series/{sid}/items")} == {"rope", "lamp", "compass"}
    assert {i["key"] for i in api.get(f"/series/{sid}/items", params={"book_id": book["id"]})} == {
        "rope",
        "lamp",
    }

    start = graph()["nodes"][0]
    api.put(f"/nodes/{start['id']}/items", [{"item_id": rope["id"], "qty": 2}])
    api.patch(f"/nodes/{start['id']}", {"on_enter": [{"op": "give", "item": "rope"}]})
    api.post(f"/nodes/{start['id']}/choices", {"label": "Climb", "condition": "has(rope)"})
    api.put(
        f"/nodes/{start['id']}/shop",
        {"items": [{"item_id": rope["id"], "price": 3, "stock": 4}], "sell_rate": 50},
    )

    used = api.get(f"/series/{sid}/where-used", params={"target_type": "item", "key": "rope"})
    roles = sorted(r["role"] for r in used["refs"])
    assert roles == ["condition", "effect.give", "placement", "shop"]
    assert used["total_qty"] == 2 + 1 + 4
    assert all(r["node_title"] == "Start" for r in used["refs"])

    # In-use entities need force to delete.
    api.delete(f"/items/{rope['id']}", expect=409)
    api.delete(f"/items/{lamp['id']}")
    api.delete(f"/items/{rope['id']}", params={"force": True})
    assert api.get(f"/nodes/{start['id']}")["items"] == []
    remaining = api.get(f"/series/{sid}/where-used", params={"target_type": "item", "key": "rope"})[
        "refs"
    ]
    assert sorted(r["role"] for r in remaining) == [
        "condition",
        "effect.give",
    ]  # dangling, flagged by validation


def test_key_rename_rewrites_references(api: Api, series: Json, graph: Callable[[], Json]) -> None:
    sid = series["id"]
    rope = api.post(f"/series/{sid}/items", {"name": "Rope"})
    orc = api.post(f"/series/{sid}/enemies", {"name": "Orc", "loot": [{"item": "rope"}]})
    api.post(
        f"/series/{sid}/tables",
        {
            "name": "Wandering",
            "dice": "1d6",
            "entries": [{"lo": 1, "hi": 6, "kind": "enemies", "enemies": [{"enemy": "orc"}]}],
        },
    )
    start = graph()["nodes"][0]
    choice = api.post(
        f"/nodes/{start['id']}/choices",
        {
            "label": "Climb",
            "condition": "has(rope) and  count(rope) > 1",
            "effects": [{"op": "take", "item": "rope"}],
        },
    )
    api.patch(
        f"/nodes/{start['id']}",
        {"on_enter": [{"op": "modify", "stat": "GOLD", "amount": "count(rope)"}]},
    )

    api.patch(f"/items/{rope['id']}", {"key": "climbing_rope"})
    c = api.get(f"/nodes/{start['id']}")["choices"][0]
    assert c["id"] == choice["id"]
    assert c["condition"] == "has(climbing_rope) and  count(climbing_rope) > 1"
    assert [(e["op"], e["item"]) for e in c["effects"]] == [("take", "climbing_rope")]
    assert api.get(f"/nodes/{start['id']}")["on_enter"][0]["amount"] == "count(climbing_rope)"
    assert api.get(f"/enemies/{orc['id']}")["loot"] == [{"item": "climbing_rope", "qty": 1}]
    assert (
        api.get(f"/series/{sid}/where-used", params={"target_type": "item", "key": "rope"})["refs"]
        == []
    )

    api.patch(f"/enemies/{orc['id']}", {"key": "orc_chief"})
    table = api.get(f"/series/{sid}/tables")[0]
    assert table["entries"][0]["enemies"][0]["enemy"] == "orc_chief"

    # Node keys rename inside visits().
    api.post(f"/nodes/{start['id']}/variants", {"label": "Again", "condition": "visits(start) > 1"})
    api.patch(f"/nodes/{start['id']}", {"key": "gate"})
    assert api.get(f"/nodes/{start['id']}")["variants"][1]["condition"] == "visits(gate) > 1"

    api.patch(f"/items/{rope['id']}", {"key": "1bad"}, expect=422)


def test_flags(api: Api, series: Json, graph: Callable[[], Json]) -> None:
    sid = series["id"]
    start = graph()["nodes"][0]
    api.patch(f"/nodes/{start['id']}", {"on_enter": [{"op": "set_flag", "flag": "RAVEN"}]})
    api.post(f"/nodes/{start['id']}/choices", {"condition": "flag(RAVEN) and not flag(FIRE)"})
    flags = {f["flag"]: f for f in api.get(f"/series/{sid}/flags")}
    assert (flags["RAVEN"]["set_count"], flags["RAVEN"]["tested_count"]) == (1, 1)
    assert flags["FIRE"]["set_count"] == 0

    assert (
        api.post(f"/series/{sid}/flags/rename", {"old": "RAVEN", "new": "CROW"}, expect=200)[
            "changed"
        ]
        == 2
    )
    node = api.get(f"/nodes/{start['id']}")
    assert node["on_enter"][0]["flag"] == "CROW"
    assert node["choices"][0]["condition"] == "flag(CROW) and not flag(FIRE)"


def test_encounters(api: Api, series: Json, graph: Callable[[], Json]) -> None:
    sid = series["id"]
    orc = api.post(
        f"/series/{sid}/enemies",
        {
            "name": "Orc",
            "stat_formulas": {
                "SKILL": "6 + level",
                "STAMINA": "5 + level * 2",
                "ARMOR": "floor(level / 2)",
            },
        },
    )
    start = graph()["nodes"][0]
    enc = api.post(
        f"/nodes/{start['id']}/encounters",
        {"label": "Orc pack", "enemies": [{"enemy_id": orc["id"], "level": 3, "count": 2}]},
    )
    assert enc["enemies"][0]["count"] == 2
    fight = api.post(
        f"/nodes/{start['id']}/choices",
        {"label": "Fight", "kind": "combat", "encounter_id": enc["id"]},
    )
    assert fight["encounter_id"] == enc["id"]

    used = api.get(f"/series/{sid}/where-used", params={"target_type": "enemy", "key": "orc"})
    assert [(r["role"], r["qty"]) for r in used["refs"]] == [("encounter", 2)]

    other = api.post(f"/series/{sid}/books", {"title": "Other"})
    other_start = api.get(f"/books/{other['id']}/graph")["nodes"][0]
    api.post(
        f"/nodes/{other_start['id']}/choices",
        {"kind": "combat", "encounter_id": enc["id"]},
        expect=422,
    )

    api.delete(f"/encounters/{enc['id']}")
    assert api.get(f"/nodes/{start['id']}")["choices"][0]["encounter_id"] is None


def test_entities_other_series_rejected(api: Api, series: Json, graph: Callable[[], Json]) -> None:
    other = api.post("/series", {"title": "Other"})
    foreign = api.post(f"/series/{other['id']}/items", {"name": "Foreign"})
    start = graph()["nodes"][0]
    api.put(f"/nodes/{start['id']}/items", [{"item_id": foreign["id"]}], expect=422)
    other_book = api.post(f"/series/{other['id']}/books", {"title": "X"})
    api.post(
        f"/series/{series['id']}/items", {"name": "Y", "book_id": other_book["id"]}, expect=422
    )


def test_all_entity_kinds(api: Api, series: Json) -> None:
    sid = series["id"]
    cases: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
        (
            "enemies",
            {"name": "Ghoul", "default_level": 3, "tags": ["undead"]},
            {"description": "Hungry"},
        ),
        (
            "items",
            {
                "name": "Potion",
                "category": "consumable",
                "use_effects": [{"op": "modify", "stat": "STAMINA", "amount": "4"}],
            },
            {"value": 5},
        ),
        (
            "tables",
            {
                "name": "Loot",
                "dice": "1d6",
                "entries": [{"lo": 1, "hi": 6, "kind": "gold", "amount": "1d6"}],
            },
            {"dice": "2d6"},
        ),
        (
            "characters",
            {"name": "Mara the Ferrywoman", "role": "guide", "relationships": []},
            {"voice": "Clipped"},
        ),
        (
            "lore",
            {"name": "The Crypt", "type": "location", "body": "Cold."},
            {"fields": {"climate": "damp"}},
        ),
    ]
    for plural, create, update in cases:
        obj = api.post(f"/series/{sid}/{plural}", create)
        changed = api.patch(f"/{plural}/{obj['id']}", update)
        for k, v in update.items():
            assert changed[k] == v
        assert api.get(f"/{plural}/{obj['id']}")["key"] == obj["key"]
        api.delete(f"/{plural}/{obj['id']}")
        api.get(f"/{plural}/{obj['id']}", expect=404)
    char = api.post(f"/series/{sid}/characters", {"name": "Mara"})
    assert char["key"] == "mara"


def test_node_lore_links(api: Api, series: Json, graph: Callable[[], Json]) -> None:
    sid = series["id"]
    crypt = api.post(f"/series/{sid}/lore", {"name": "The Crypt", "type": "location"})
    mara = api.post(f"/series/{sid}/characters", {"name": "Mara"})
    start = graph()["nodes"][0]
    node = api.patch(
        f"/nodes/{start['id']}",
        {"location_id": crypt["id"], "character_ids": [mara["id"], mara["id"]]},
    )
    assert node["character_ids"] == [mara["id"]]
    used = api.get(f"/series/{sid}/where-used", params={"target_type": "character", "key": "mara"})
    assert [r["role"] for r in used["refs"]] == ["appears"]
    api.delete(f"/characters/{mara['id']}", expect=409)
