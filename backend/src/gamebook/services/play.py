"""The in-app player: replay the reader's inputs and describe where they are.

The server keeps no session. The client sends everything the reader has done
(actions and debug inputs) and gets back the resulting view, so reloads, back
and restart are trivial and every playthrough is reproducible. If the book
changed so an input no longer applies, replay stops there and says so.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.core.engine import Action, Game, GameError
from gamebook.core.engine.narrate import Names, narrate
from gamebook.core.model import BookSnapshot
from gamebook.db.models import Appendix, Asset, Map, Node, ProseVersion
from gamebook.schemas.playtest import (
    ActionInput,
    ForceInput,
    JumpInput,
    Option,
    PlayAction,
    PlayArt,
    PlayCodex,
    PlayCombat,
    PlayEnemy,
    PlayEvent,
    PlayIn,
    PlayInput,
    PlayItem,
    PlayMap,
    PlayMarker,
    PlayNode,
    PlayOut,
    PlayProgress,
    PlayStat,
    SetInput,
)
from gamebook.services import art, snapshot
from gamebook.services.errors import InvalidError


def _apply(game: Game, inp: PlayInput) -> None:
    match inp:
        case ActionInput(type=t, target=target):
            game.step(Action(t, target))
        case JumpInput(node_id=node_id):
            game.debug_jump(node_id)
        case SetInput(stats=stats, items=items, flags=flags):
            game.debug_set(stats=stats, items=items, flags=flags)
        case ForceInput(total=total):
            game.force_roll(total)


def start_game(book: BookSnapshot, data: PlayIn) -> Game:
    try:
        game = Game(book, data.tier, data.seed)
        game.start(character_class=data.character_class, fixed_stats=data.fixed_stats)
    except GameError as exc:
        raise InvalidError(str(exc)) from exc
    return game


def view(
    game: Game,
    *,
    turns: list[int],
    applied: int,
    error: str | None,
    beat_notes: dict[str, str],
    prose: dict[str, str] | None = None,
) -> PlayOut:
    """Describe a game. ``turns[i]`` is the input index that produced ``game.log[i]``."""
    s, tier, book = game.state, game.tier, game.book
    names = Names.for_game(game)
    node = game.node
    acts = {a.id: a.title for a in book.acts}
    variant = next((v for v in node.variants if v.id == s.variant_id), None) if node else None
    effective = game.effective_stats()
    equipped = set(s.equipped.values())
    items_by_key = {i.key: i for i in book.items}
    return PlayOut(
        tier=s.tier,
        seed=game.seed,
        applied=applied,
        error=error,
        ended=s.ended,
        node=PlayNode(
            id=node.id,
            key=node.key,
            title=node.title,
            beat_notes=beat_notes.get(node.id, ""),
            prose=(prose or {}).get(s.variant_id or ""),
            act_title=acts.get(node.act_id),
            variant_label=variant.label if variant else None,
            ending_kind=node.ending_kind,
            ending_grade=node.ending_grade,
        )
        if node
        else None,
        stats=[
            PlayStat(
                key=k,
                label=sd.label,
                kind=sd.kind,
                value=s.stats.get(k, 0),
                effective=effective.get(k, s.stats.get(k, 0)),
                max=s.max_stats.get(k),
            )
            for k, sd in tier.stats.items()
            if "player" in sd.applies_to
        ],
        currency=game.currency,
        progress=_progress(game),
        character_class=s.character_class,
        skills=[Option(key=k, label=names.skills.get(k, k)) for k in sorted(s.skills)],
        items=[
            PlayItem(
                key=k,
                name=items_by_key[k].name if k in items_by_key else k,
                category=items_by_key[k].category if k in items_by_key else "treasure",
                count=n,
                slot=items_by_key[k].slot if k in items_by_key else None,
                equipped=k in equipped,
            )
            for k, n in sorted(s.items.items())
            if n > 0
        ],
        flags=sorted(s.flags),
        combat=PlayCombat(
            round=s.combat.round,
            flee_allowed=s.combat.flee_allowed,
            enemies=[
                PlayEnemy(key=e.key, name=names.enemy(e.key), level=e.level, stats=e.stats)
                for e in s.combat.enemies
            ],
        )
        if s.combat
        else None,
        actions=[
            PlayAction(
                type=a.type, target=a.target, label=a.label, enabled=a.enabled, reason=a.reason
            )
            for a in game.actions()
        ],
        events=[
            PlayEvent(type=e.type, text=narrate(e, names), turn=turns[i], data=e.data)
            for i, e in enumerate(game.log)
        ],
        classes=[Option(key=k, label=c.label) for k, c in tier.classes.items()],
        class_in_story=tier.class_choice == "story",
        steps=s.steps,
    )


def _progress(game: Game) -> PlayProgress | None:
    pr = game.tier.progression
    if (
        not pr.enabled()
        or pr.xp_stat not in game.tier.stats
        or pr.level_stat not in game.tier.stats
    ):
        return None
    assert pr.xp_stat is not None
    assert pr.level_stat is not None
    return PlayProgress(
        xp_stat=pr.xp_stat,
        level_stat=pr.level_stat,
        level=game.state.stats.get(pr.level_stat, 0),
        xp=game.state.stats.get(pr.xp_stat, 0),
        xp_needed=game.xp_needed(),
    )


def prose_for(session: Session, variant_ids: list[str]) -> dict[str, str]:
    """Approved prose per variant."""
    if not variant_ids:
        return {}
    rows = session.execute(
        select(ProseVersion.variant_id, ProseVersion.text).where(
            ProseVersion.variant_id.in_(variant_ids), ProseVersion.status == "approved"
        )
    )
    return {str(r[0]): str(r[1]) for r in rows}


def beat_notes_for(session: Session, node_ids: list[str]) -> dict[str, str]:
    if not node_ids:
        return {}
    rows = session.execute(select(Node.id, Node.beat_notes).where(Node.id.in_(node_ids)))
    return {str(r[0]): str(r[1]) for r in rows}


def play(session: Session, book_id: str, data: PlayIn) -> PlayOut:
    book = snapshot.book_snapshot(session, book_id)
    game = start_game(book, data)
    turns = [-1] * len(game.log)
    applied, error = 0, None
    for i, inp in enumerate(data.inputs):
        mark = len(game.log)
        try:
            _apply(game, inp)
        except GameError as exc:
            error = f"Step {i + 1} no longer applies: {exc}"
            del game.log[mark:]
            break
        turns += [i] * (len(game.log) - mark)
        applied += 1
    ids = [game.state.node_id] if game.state.node_id else []
    out = view(
        game,
        turns=turns,
        applied=applied,
        error=error,
        beat_notes=beat_notes_for(session, ids),
        prose=prose_for(session, [game.state.variant_id] if game.state.variant_id else []),
    )
    s = game.state
    if s.node_id:
        out.art = [
            PlayArt.model_validate(a)
            for a in art.player_art(session, s.node_id, s.variant_id, s.tier)
        ]
    out.maps = _maps(session, book, game)
    out.codex = _codex(session, book_id, game)
    return out


def _maps(session: Session, book: BookSnapshot, game: Game) -> list[PlayMap]:
    """The book's maps with the markers this reader can see (``visible_if`` holds)."""
    rows = list(
        session.scalars(
            select(Map)
            .where(
                Map.series_id == book.series_id,
                (Map.book_id.is_(None)) | (Map.book_id == book.book_id),
            )
            .order_by(Map.title)
        )
    )
    alts = dict(
        session.execute(
            select(Asset.id, Asset.alt_text).where(
                Asset.id.in_({m.asset_id for m in rows if m.asset_id})
            )
        ).all()
    )
    here = game.state.node_id
    return [
        PlayMap(
            id=m.id,
            title=m.title,
            url=f"/api/assets/{m.asset_id}/file" if m.asset_id else None,
            alt=alts.get(m.asset_id or "", "") or m.title,
            markers=[
                PlayMarker(
                    id=mk["id"],
                    x=mk["x"],
                    y=mk["y"],
                    label=mk.get("label", ""),
                    here=bool(here and mk.get("node_id") == here),
                )
                for mk in m.markers
                if game.holds(mk.get("visible_if"))
            ],
        )
        for m in rows
    ]


def _codex(session: Session, book_id: str, game: Game) -> PlayCodex:
    """Enemies fought and items held or found so far (codex entries unlock as met)."""
    enemies: set[str] = set()
    items = {k for k, n in game.state.items.items() if n > 0}
    for e in game.log:
        d = e.data
        if e.type == "combat_start":
            enemies.update(x["key"].partition("#")[0] for x in d.get("enemies", []))
        elif d.get("item") and (
            e.type in ("item_taken", "item_bought")
            or (e.type == "effect" and d.get("op") == "give")
        ):
            items.add(d["item"])
    available = session.scalar(
        select(Appendix.id)
        .where(
            Appendix.book_id == book_id,
            Appendix.enabled,
            Appendix.kind != "sheet",
        )
        .limit(1)
    )
    return PlayCodex(enemies=sorted(enemies), items=sorted(items), available=available is not None)
