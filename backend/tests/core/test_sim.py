"""Bots, batch statistics, replay, the coverage walker and debug hooks."""

from __future__ import annotations

import pytest

from gamebook.core.engine import Action, Game, GameError
from gamebook.core.engine.narrate import Names, narrate
from gamebook.core.model import Encounter, EncounterEnemy
from gamebook.core.sim import BOT_NAMES, play_run, replay_run, summarize, walk

from .builders import book, ending, goto, node, with_choices
from .engine_book import choice, engine_book


@pytest.mark.parametrize("bot", BOT_NAMES)
@pytest.mark.parametrize("tier", ["basic", "medium", "advanced"])
def test_bots_finish_and_replay_exactly(bot: str, tier: str) -> None:
    book = engine_book()
    for seed in range(15):
        rec = play_run(book, tier, seed, bot, max_steps=300)  # type: ignore[arg-type]
        assert rec.outcome != "error", rec.error_sample
        assert len(rec.picks) == rec.steps
        game = replay_run(book, tier, seed, rec.picks)
        assert game.state.steps == rec.steps
        assert (game.state.ended or "max_steps") == rec.outcome
        assert game.state.node_id == rec.last_node_id


def test_runs_are_deterministic() -> None:
    book = engine_book()
    a = play_run(book, "medium", 7, "explorer", max_steps=300)
    b = play_run(book, "medium", 7, "explorer", max_steps=300)
    assert a.stored() == b.stored()


def test_replay_detects_a_changed_book() -> None:
    with pytest.raises(GameError, match="no longer matches"):
        replay_run(engine_book(), "basic", 1, [99])


def test_summary_numbers_are_consistent() -> None:
    book = engine_book()
    recs = [play_run(book, "basic", s, "random", max_steps=300, index=s) for s in range(200)]
    s = summarize(book, recs)
    assert s["runs"] == 200
    assert sum(s["outcomes"].values()) == 200
    assert s["win_rate"] == s["outcomes"].get("victory", 0) / 200
    start = book.start_node_id
    assert start is not None
    assert s["node_visits"][start] == 200  # every run starts there
    assert s["coverage"]["nodes_visited"] == len(s["node_visits"])
    assert s["coverage"]["nodes_visited"] + len(s["coverage"]["unvisited"]) == len(book.nodes)
    deaths = sum(v for k, v in s["outcomes"].items() if k in ("death", "defeated"))
    assert sum(s["deaths_by_node"].values()) == deaths
    assert sum(s["death_causes"].values()) == deaths
    for item in s["items"].values():
        assert 0 <= item["wins_with"] <= item["held_runs"] <= 200
    assert s["acts"][0]["reached"] == 200


def test_explorer_covers_more_than_random() -> None:
    book = engine_book()

    def coverage(bot: str) -> int:
        recs = [play_run(book, "advanced", s, bot, max_steps=300) for s in range(40)]  # type: ignore[arg-type]
        return int(summarize(book, recs)["coverage"]["nodes_visited"])

    assert coverage("explorer") >= coverage("random")


def test_walker_finds_gated_content_but_not_impossible_content() -> None:
    book = engine_book()
    ids = {n.key: n.id for n in book.nodes}
    basic = walk(book, "basic", samples=1, max_states=10_000)
    assert not basic.truncated
    assert ids["vault"] in basic.reached  # needs the iron key: save up 50 gold, buy it
    assert ids["secret"] not in basic.reached  # flag(NEVER) is never set
    assert ids["elite"] not in basic.reached  # advanced tier only
    assert {ids["end"], ids["dead"]} <= set(basic.endings)
    assert ids["elite"] in walk(book, "advanced", samples=1, max_states=300).reached


def test_walker_explores_fleeing() -> None:
    """Review regression: fights were always fought to the end, so flee-only content was missed."""
    from dataclasses import replace

    start = replace(
        with_choices(
            node("start"),
            choice(
                "fight",
                "start",
                "combat",
                {"win": "end", "lose": "dead", "flee": "hideout"},
                encounter_id="enc",
                flee_allowed=True,
            ),
        ),
        encounters=(Encounter("enc", "Orc", enemies=(EncounterEnemy("e-orc", level=1),)),),
    )
    b = book(
        start,
        with_choices(node("hideout"), goto("hideout", "end")),
        ending("end"),
        ending("dead", kind="death"),
    )
    assert "hideout" in walk(b, "basic", samples=2).reached


def test_walker_sees_visit_counts() -> None:
    """Review regression: visits() gates looked identical on every visit."""
    b = book(
        with_choices(
            node("start"),
            goto("start", "side", "Wander"),
            goto("start", "secret", "Notice the door", condition="visits(start) > 1"),
        ),
        with_choices(node("side"), goto("side", "start", "Back")),
        with_choices(node("secret"), goto("secret", "end")),
        ending("end"),
    )
    assert "secret" in walk(b, "basic", samples=1).reached


def test_walker_is_bounded() -> None:
    res = walk(engine_book(), "basic", max_states=3)
    assert res.truncated
    assert res.states == 3


def test_clone_is_independent() -> None:
    g = Game(engine_book(), "basic", 3)
    g.start()
    c = g.clone()
    c.step(c.available()[0])
    assert g.state.steps == 0
    assert c.state.steps == 1


def test_debug_hooks() -> None:
    book = engine_book()
    ids = {n.key: n.id for n in book.nodes}
    g = Game(book, "basic", 1)
    g.start()
    g.debug_jump(ids["hall"])
    assert g.state.node_id == ids["hall"]
    g.force_roll(12)
    gamble = next(a for a in g.available() if a.label.startswith("gamble") or a.target == "gamble")
    g.step(gamble)
    assert g.state.node_id == ids["den"]  # 12 is "high"
    rolls = [e for e in g.log if e.type == "roll" and e.data.get("forced")]
    assert rolls
    assert rolls[0].data["total"] == 12
    g.debug_set(stats={"STAMINA": 0})
    assert g.state.ended == "defeated"
    g.debug_jump(ids["start"])  # still at 0 STAMINA: defeated again on arrival
    assert g.state.ended == "defeated"
    g.debug_set(stats={"STAMINA": 10})
    g.debug_jump(ids["start"])  # debug can resume a finished game
    assert g.state.ended is None
    g.debug_set(items={"iron_key": 1}, flags={"NEVER": True})
    assert {"start->vault", "start->secret"} <= {a.target for a in g.available()}
    with pytest.raises(GameError):
        g.debug_jump("nope")


def test_every_event_narrates_without_error() -> None:
    book = engine_book()
    for tier in ("basic", "medium", "advanced"):
        for seed in range(20):
            g = Game(book, tier, seed)
            g.start()
            names = Names.for_game(g)
            while not g.state.ended and g.state.steps < 200:
                g.step(g.available()[seed % len(g.available())])
            for e in g.log:
                line = narrate(e, names)
                assert line is None or line.strip()


def test_unknown_action_still_rejected() -> None:
    g = Game(engine_book(), "basic", 1)
    g.start()
    with pytest.raises(GameError):
        g.step(Action("choose", "nope"))


def test_deaths_blame_only_a_fight_lost_in_the_same_step() -> None:
    """Review regression: a survived loss used to be blamed for a later death."""
    from gamebook.core.engine import Event
    from gamebook.core.sim.batch import RunRecord, _Observer

    def fight(*hits: tuple[str, str]) -> list[Event]:
        return [
            Event("action", {"action": "choose", "target": "c"}),
            Event("combat_start", {"enemies": [{"key": "orc"}, {"key": "rat#1"}]}),
            *(Event("combat_round", {"enemy": e, "hit": h}) for e, h in hits),
            Event("combat_end", {"outcome": "lose"}),
        ]

    obs = _Observer(RunRecord(0, 0, "", None, None, 0, []))
    obs.see(fight(("orc", "player"), ("rat#1", "player")))
    assert obs.lost_to == "rat"  # the last enemy to land a blow
    obs.see([Event("action", {"action": "choose", "target": "pit"})])
    assert obs.lost_to is None  # survived; a later death isn't the rat's
