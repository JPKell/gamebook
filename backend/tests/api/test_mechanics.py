"""Mechanics designer support and the combat lab over HTTP."""

from typing import Any

from .conftest import Api, Json


def active_rules(api: Api, series: Json) -> Json:
    rs: Json = next(r for r in api.get(f"/series/{series['id']}/rule-systems") if r["is_active"])
    return rs


def test_tier_view_shows_provenance(api: Api, series: Json) -> None:
    rs = active_rules(api, series)
    view = api.get(f"/rule-systems/{rs['id']}/tiers/medium")
    assert view["chain"] == ["basic", "medium"]
    stats = {s["key"]: (s["introduced"], s["origin"]) for s in view["stats"]}
    assert stats["SKILL"] == ("basic", "basic")
    assert stats["ARMOR"] == ("medium", "medium")
    assert view["combat_origin"]["player_attack"] == "basic"
    assert [h["origin"] for h in view["damage_hooks"]] == ["medium"]
    assert {s["slot"]: s["origin"] for s in view["slots"]}["weapon"] == "medium"

    adv = api.get(f"/rule-systems/{rs['id']}/tiers/advanced")
    assert [h["origin"] for h in adv["damage_hooks"]] == ["medium", "advanced"]
    assert {c["key"] for c in adv["classes"]} == {"ranger", "rogue", "scholar"}

    # Override SKILL in medium: still introduced by basic, but now in effect from medium.
    definition = rs["definition"]
    definition["tiers"][1]["stats"].append(
        {"key": "SKILL", "label": "Prowess", "applies_to": ["player", "enemy"], "initial": "2d6"}
    )
    api.patch(f"/rule-systems/{rs['id']}", {"definition": definition})
    view = api.get(f"/rule-systems/{rs['id']}/tiers/medium")
    skill = next(s for s in view["stats"] if s["key"] == "SKILL")
    assert (skill["introduced"], skill["origin"], skill["label"]) == ("basic", "medium", "Prowess")
    api.get(f"/rule-systems/{rs['id']}/tiers/legendary", expect=422)


def test_rule_system_problems(api: Api, series: Json) -> None:
    rs = active_rules(api, series)
    assert api.get(f"/rule-systems/{rs['id']}/problems")["counts"] == {
        "errors": 0,
        "warnings": 0,
        "info": 0,
    }
    definition = rs["definition"]
    definition["tiers"][0]["combat"]["player_attack"] = "2d6 + player.SKIL"
    api.patch(f"/rule-systems/{rs['id']}", {"definition": definition})
    res = api.get(f"/rule-systems/{rs['id']}/problems")
    assert res["counts"]["errors"] >= 1
    assert any("SKIL" in p["message"] for p in res["problems"])


def lab(api: Api, series: Json, **body: Any) -> Any:
    expect = body.pop("expect", 200)
    payload = {"tier": "basic", "runs": 500, "seed": 7} | body
    return api.post(f"/series/{series['id']}/combat-lab", payload, expect=expect)


def test_combat_lab_with_series_enemy_and_adhoc(api: Api, series: Json) -> None:
    orc = api.post(
        f"/series/{series['id']}/enemies",
        {
            "name": "Orc",
            "stat_formulas": {
                "SKILL": "5 + level",
                "STAMINA": "4 + level * 2",
                "ARMOR": "floor(level / 2)",
            },
        },
    )
    res = lab(api, series, enemies=[{"enemy_id": orc["id"], "level": 3}])
    assert res["enemies"] == [
        {"name": "Orc", "level": 3, "count": 1, "stats": {"SKILL": 8, "STAMINA": 10}}
    ]
    assert res["wins"] + res["losses"] + res["stalemates"] == 500
    assert 0 < res["win_rate"] < 1
    assert res["damage_stat"] == "STAMINA"
    assert sum(res["rounds"]["histogram"].values()) == 500
    assert res == lab(api, series, enemies=[{"enemy_id": orc["id"], "level": 3}])  # deterministic

    strong = lab(
        api,
        series,
        enemies=[{"stats": {"SKILL": 8, "STAMINA": 10}}],
        player={"mode": "fixed", "stats": {"SKILL": 12, "STAMINA": 20}},
    )
    weak = lab(
        api,
        series,
        enemies=[{"stats": {"SKILL": 8, "STAMINA": 10}}],
        player={"mode": "fixed", "stats": {"SKILL": 6, "STAMINA": 8}},
    )
    assert strong["win_rate"] > weak["win_rate"]
    medium = lab(
        api, series, tier="medium", enemies=[{"enemy_id": orc["id"], "level": 3, "count": 2}]
    )
    assert medium["enemies"][0]["stats"]["ARMOR"] == 1


def test_combat_lab_validation(api: Api, series: Json) -> None:
    other = api.post("/series", {"title": "Other"})
    foreign = api.post(f"/series/{other['id']}/enemies", {"name": "Far"})
    lab(api, series, enemies=[{"enemy_id": foreign["id"]}], expect=422)
    lab(api, series, enemies=[{"stats": {"SKILL": 1}, "enemy_id": "x"}], expect=422)
    lab(api, series, enemies=[], expect=422)
    lab(api, series, enemies=[{"stats": {}}], runs=50_000, expect=422)
    lab(api, series, tier="legendary", enemies=[{"stats": {}}], expect=422)
    rs = active_rules(api, series)
    definition = rs["definition"]
    definition["tiers"][0]["combat"].pop("player_attack")
    api.patch(f"/rule-systems/{rs['id']}", {"definition": definition})
    err = lab(api, series, enemies=[{"stats": {"SKILL": 5}}], expect=422)
    assert "combat" in err["detail"]
    other_rs = api.get(f"/series/{other['id']}/rule-systems")[0]
    lab(api, series, rule_system_id=other_rs["id"], enemies=[{"stats": {}}], expect=422)


def test_level_sweep(api: Api, series: Json) -> None:
    res = api.post(
        f"/series/{series['id']}/combat-lab/sweep",
        {
            "tier": "medium",
            "name": "Orc",
            "formulas": {
                "SKILL": "5 + level",
                "STAMINA": "4 + level * 2",
                "ARMOR": "floor(level / 2)",
            },
            "level_from": 1,
            "level_to": 8,
            "runs": 300,
        },
        expect=200,
    )
    assert res["name"] == "Orc"
    assert [p["level"] for p in res["points"]] == list(range(1, 9))
    assert res["points"][0]["win_rate"] > res["points"][-1]["win_rate"]
    assert res["points"][2]["enemy"] == {"SKILL": 8, "STAMINA": 10, "ARMOR": 1}
    api.post(
        f"/series/{series['id']}/combat-lab/sweep",
        {"tier": "basic", "formulas": {}, "level_from": 1, "level_to": 30, "runs": 5000},
        expect=422,
    )
    api.post(
        f"/series/{series['id']}/combat-lab/sweep",
        {"tier": "basic", "formulas": {}, "level_from": 5, "level_to": 2},
        expect=422,
    )
