"""The game engine: plays one book at one tier, deterministically from a seed.

    game = Game(book, tier="basic", seed=42)
    game.start()
    while not game.state.ended:
        game.step(game.available()[0])

Everything that happens is appended to ``game.log`` as an ``Event``; every die
rolled is in ``game.rng.history``. The same book, tier, seed, creation options
and action list always produce the same events (see ``trace.py``).
"""

from __future__ import annotations

import copy
import math
from collections.abc import Sequence
from fractions import Fraction

from gamebook.core import gbx
from gamebook.core.effects import (
    ChooseClass,
    ClearFlag,
    Effect,
    EquipItem,
    GiveItem,
    LearnSkill,
    ModifyStat,
    SetFlag,
    SetStat,
    TakeItem,
    fires_once,
)
from gamebook.core.engine.combat import (
    MAX_ROUNDS,
    CombatRules,
    enemies_defeated,
    enemy_stats,
    fight_round,
    player_defeated,
)
from gamebook.core.engine.env import GameEnv, compiled_bool, compiled_int
from gamebook.core.engine.events import Action, Event
from gamebook.core.engine.state import Combatant, CombatState, GameState
from gamebook.core.model import BookSnapshot, Choice, Encounter, Item, Node
from gamebook.core.rules.schema import EffectiveTier, StartingItem, StatBonus, effective_tier

#: Level-ups handled at once (guards against a formula that makes levels free).
MAX_LEVEL_UPS = 100


class GameError(ValueError):
    """An action that isn't allowed right now, or a book that can't be played."""


class Game:
    def __init__(self, book: BookSnapshot, tier: str, seed: int) -> None:
        if book.rules is None:
            raise GameError("The series has no active rule system")
        self.book = book
        self.tiers = book.rules.tier_keys()
        if tier not in self.tiers:
            raise GameError(f"Unknown tier {tier!r}")
        self.tier: EffectiveTier = effective_tier(book.rules, tier)
        self.seed = seed
        self.rng = gbx.SeededRng(seed)
        self.state = GameState(tier=tier)
        self.log: list[Event] = []
        self._pending_errors: list[Event] = []
        #: Debug: totals the next dice rolls (choices, tests, tables, stats) will produce.
        self.forced_rolls: list[int] = []
        try:
            self.combat_rules = CombatRules.from_tier(self.tier)
        except gbx.GbxSyntaxError as exc:
            self.combat_rules = None
            self._pending_errors.append(
                Event("error", {"where": "combat rules", "message": str(exc)})
            )
        self.currency = next((k for k, s in self.tier.stats.items() if s.kind == "resource"), None)

        self._nodes = {n.id: n for n in book.nodes}
        available = [i for i in book.items if book.available(i)]
        self._items_by_id = {i.id: i for i in available}
        self._items = {i.key: i for i in available}
        self._enemies_by_id = {e.id: e for e in book.enemies if book.available(e)}
        self._enemies = {e.key: e for e in self._enemies_by_id.values()}
        self._tables = {t.id: t for t in book.tables if book.available(t)}
        self._env = GameEnv(self.tiers, tier, self.stat, self._ref)

    def clone(self, seed: int | None = None) -> Game:
        """An independent copy sharing the (immutable) book; optionally reseeded dice."""
        g = copy.copy(self)
        g.state = copy.deepcopy(self.state)
        g.rng = gbx.SeededRng(seed) if seed is not None else copy.deepcopy(self.rng)
        g.log = []
        g._pending_errors = []
        g.forced_rolls = list(self.forced_rolls)
        g._env = GameEnv(self.tiers, self.state.tier, g.stat, g._ref)
        return g

    # ── queries ──────────────────────────────────────────────────────────

    @property
    def node(self) -> Node | None:
        return self._nodes.get(self.state.node_id or "")

    def tier_allows(self, min_tier: str | None) -> bool:
        if min_tier is None or min_tier not in self.tiers:
            return min_tier is None
        return self.tiers.index(min_tier) <= self.tiers.index(self.state.tier)

    def stat(self, key: str) -> int:
        """Effective player stat: base value plus item modifiers."""
        value = self.state.stats.get(key, 0)
        for item_key, count in self.state.items.items():
            if count <= 0:
                continue
            item = self._items.get(item_key)
            if item is None or not item.modifiers:
                continue
            if item.slot and self.state.equipped.get(item.slot) != item_key:
                continue
            for m in item.modifiers:
                if m.stat == key and self.tier_allows(m.min_tier):
                    value += self._int(m.amount, f"item {item_key} modifier", rng=False)
        return value

    def effective_stats(self) -> dict[str, int]:
        # Definition order (not a set's), so error events come out in a fixed order.
        return {k: self.stat(k) for k, sd in self.tier.stats.items() if "player" in sd.applies_to}

    def _ref(self, func: str, key: str) -> int | bool:
        s = self.state
        match func:
            case "has":
                return s.items.get(key, 0) > 0
            case "count":
                return s.items.get(key, 0)
            case "equipped":
                return key in s.equipped.values()
            case "flag":
                return key in s.flags
            case "skill":
                return key in s.skills
            case "class":
                return s.character_class == key
            case "visits":
                return s.visits.get(key, 0)
        return False

    # ── expression helpers (content errors become events, never crashes) ──

    def _error(self, where: str, exc: Exception) -> None:
        if self._quiet:
            return
        self.log.append(Event("error", {"where": where, "message": str(exc)}))

    _quiet = False

    def _int(self, src: str, where: str, *, rng: bool = True, env: GameEnv | None = None) -> int:
        try:
            return compiled_int(src)(env or self._env, self.rng if rng else None)
        except (gbx.GbxSyntaxError, gbx.GbxEvalError) as exc:
            self._error(where, exc)
            return 0

    def holds(self, src: str | None) -> bool:
        """Whether a condition holds now, with no side effects (errors count as false)."""
        if not src:
            return True
        try:
            return compiled_bool(src)(self._env, None)
        except (gbx.GbxSyntaxError, gbx.GbxEvalError):
            return False

    def _bool(self, src: str | None, where: str, env: GameEnv | None = None) -> bool:
        if not src:
            return True
        try:
            return compiled_bool(src)(env or self._env, None)
        except (gbx.GbxSyntaxError, gbx.GbxEvalError) as exc:
            self._error(where, exc)
            return False

    def _roll(self, src: str, purpose: str) -> int:
        if self.forced_rolls:
            total = self.forced_rolls.pop(0)
            self.log.append(
                Event(
                    "roll",
                    {"purpose": purpose, "expr": src, "faces": [], "total": total, "forced": True},
                )
            )
            return total
        before = len(self.rng.history)
        total = self._int(src, purpose)
        faces = [f for _, _, fs in self.rng.history[before:] for f in fs]
        self.log.append(
            Event("roll", {"purpose": purpose, "expr": src, "faces": faces, "total": total})
        )
        return total

    # ── setup ────────────────────────────────────────────────────────────

    def start(
        self,
        *,
        character_class: str | None = None,
        fixed_stats: dict[str, int] | None = None,
    ) -> list[Event]:
        """Create the character and enter the start node."""
        mark = len(self.log)
        if self.state.node_id is not None:
            raise GameError("The game has already started")
        self.log += self._pending_errors
        for key, sd in self.tier.stats.items():
            if "player" not in sd.applies_to:
                continue
            if fixed_stats and key in fixed_stats:
                value = fixed_stats[key]
            else:
                value = self._roll(sd.initial, f"initial {key}")
            self.state.stats[key] = value
            if sd.max_is_initial:
                self.state.max_stats[key] = value
            elif sd.max is not None:
                self.state.max_stats[key] = sd.max
        # At "story" tiers the class is picked later, by a choose-class effect.
        if self.tier.classes and self.tier.class_choice == "start":
            chosen = character_class or next(iter(self.tier.classes))
            cls = self.tier.classes.get(chosen)
            if cls is None:
                raise GameError(f"Unknown class {chosen!r}")
            self.state.character_class = cls.key
            self.state.skills.update(cls.skills)
            for b in cls.modifiers:
                self._bonus(b, f"class {cls.key} bonus")
        self.log.append(
            Event(
                "character_created",
                {
                    "stats": dict(sorted(self.state.stats.items())),
                    "class": self.state.character_class,
                },
            )
        )
        cls = self.tier.classes.get(self.state.character_class or "")
        self._starting_items([*self.tier.starting_items, *(cls.starting_items if cls else ())])
        start = self._nodes.get(self.book.start_node_id or "")
        if start is None:
            self._end("stuck", None, "The book has no start node")
        else:
            self._enter(start)
        return self.log[mark:]

    def _starting_items(self, entries: Sequence[StartingItem]) -> None:
        for si in entries:
            item = self._items.get(si.item)
            if item is None:
                self._error("starting items", gbx.GbxEvalError(f"unknown item {si.item}"))
                continue
            got = self._give(item.key, si.qty)
            self.log.append(
                Event("effect", {"source": "start", "op": "give", "item": item.key, "qty": got})
            )
            if si.equip and item.slot in self.tier.slots and self.state.items.get(item.key, 0) > 0:
                self.state.equipped[item.slot] = item.key
                self.log.append(
                    Event("effect", {"source": "start", "op": "equip", "item": item.key})
                )

    # ── progression ──────────────────────────────────────────────────────

    def level(self) -> int:
        """The reader's level (1 when the rules have no levels)."""
        key = self.tier.progression.level_stat
        return self.state.stats.get(key, 1) if key and key in self.tier.stats else 1

    def xp_needed(self) -> int | None:
        """XP the next level costs, for display (None without levels or at the top)."""
        pr = self.tier.progression
        if not pr.enabled() or pr.level_stat not in self.tier.stats:
            return None
        level = self.state.stats.get(pr.level_stat or "", 0)
        cap = self.state.max_stats.get(pr.level_stat or "")
        if (pr.max_level is not None and level >= pr.max_level) or (
            cap is not None and level >= cap
        ):
            return None
        quiet, self._quiet = self._quiet, True
        try:
            env = self._env.with_(variables={"level": Fraction(level)})
            need = self._int(pr.xp_to_next or "0", "XP for the next level", rng=False, env=env)
        finally:
            self._quiet = quiet
        return need if need > 0 else None

    def _bonus(self, bonus: StatBonus, where: str) -> int:
        """Raise a player stat (and a starting-value maximum) by a bonus; returns the change."""
        sd = self.tier.stats.get(bonus.stat)
        if sd is None or "player" not in sd.applies_to:
            return 0
        env = self._env.with_(variables={"level": Fraction(self.level())})
        amount = self._int(bonus.amount, where, env=env)
        if sd.max_is_initial and bonus.stat in self.state.max_stats:
            self.state.max_stats[bonus.stat] += amount
        before = self.state.stats.get(bonus.stat, 0)
        return self._set_stat(bonus.stat, before + amount) - before

    def _award_xp(self, enemies: Sequence[Combatant]) -> None:
        pr = self.tier.progression
        if not pr.enabled() or not pr.xp_award or pr.xp_stat not in self.tier.stats:
            return
        total = 0
        for e in enemies:
            env = self._env.with_(
                variables={"enemy_level": Fraction(e.level), "level": Fraction(self.level())}
            )
            total += self._int(pr.xp_award, "XP award", env=env)
        before = self.state.stats.get(pr.xp_stat, 0)
        after = self._set_stat(pr.xp_stat, before + total)
        self.log.append(
            Event("xp_gained", {"stat": pr.xp_stat, "amount": after - before, "value": after})
        )
        self._check_level_up()

    def _check_level_up(self) -> None:
        pr = self.tier.progression
        xp_key, level_key = pr.xp_stat, pr.level_stat
        if (
            not pr.enabled()
            or xp_key not in self.tier.stats
            or level_key not in self.tier.stats
            or xp_key == level_key
        ):
            return
        assert xp_key is not None
        assert level_key is not None
        assert pr.xp_to_next is not None
        for _ in range(MAX_LEVEL_UPS):
            level = self.state.stats.get(level_key, 0)
            cap = self.state.max_stats.get(level_key)
            if (pr.max_level is not None and level >= pr.max_level) or (
                cap is not None and level >= cap
            ):
                return
            env = self._env.with_(variables={"level": Fraction(level)})
            need = self._int(pr.xp_to_next, "XP for the next level", rng=False, env=env)
            xp = self.state.stats.get(xp_key, 0)
            if need <= 0 or xp < need:
                return
            self._set_stat(xp_key, xp - need)
            new = self._set_stat(level_key, level + 1)
            self.log.append(
                Event(
                    "level_up",
                    {"stat": level_key, "level": new, "xp": self.state.stats.get(xp_key, 0)},
                )
            )
            for b in pr.level_up or []:
                change = self._bonus(b, "level-up bonus")
                self.log.append(
                    Event(
                        "effect",
                        {
                            "source": "level_up",
                            "op": "modify",
                            "stat": b.stat,
                            "change": change,
                            "value": self.state.stats.get(b.stat, 0),
                        },
                    )
                )

    # ── effects ──────────────────────────────────────────────────────────

    def _set_stat(self, key: str, value: int) -> int:
        sd = self.tier.stats.get(key)
        if sd is not None:
            if sd.min is not None:
                value = max(sd.min, value)
            cap = self.state.max_stats.get(key)
            if cap is not None:
                value = min(cap, value)
        self.state.stats[key] = value
        return value

    def _give(self, key: str, qty: int) -> int:
        item = self._items.get(key)
        have = self.state.items.get(key, 0)
        new = have + qty
        if item is not None and item.max_stack is not None:
            new = min(new, item.max_stack)
        self.state.items[key] = new
        return new - have

    def _take(self, key: str, qty: int) -> int:
        have = self.state.items.get(key, 0)
        new = max(0, have - qty)
        self.state.items[key] = new
        if new == 0:
            for slot, k in list(self.state.equipped.items()):
                if k == key:
                    del self.state.equipped[slot]
        return have - new

    def _apply(
        self,
        effects: Sequence[Effect],
        source: str,
        *,
        respect_once: bool = True,
        check_defeat: bool = True,
    ) -> None:
        xp_key = self.tier.progression.xp_stat
        xp_touched = False
        for i, eff in enumerate(effects):
            if not self.tier_allows(eff.min_tier):
                continue
            once_key = f"{source}:{i}"
            if respect_once and fires_once(eff):
                if once_key in self.state.fired:
                    continue
                self.state.fired.add(once_key)
            where = f"{source} effect {i + 1}"
            data: dict[str, object] = {"source": source, "op": eff.op}
            match eff:
                case ModifyStat(stat=stat, amount=src):
                    delta = self._int(src, where)
                    before = self.state.stats.get(stat, 0)
                    after = self._set_stat(stat, before + delta)
                    data.update(stat=stat, change=after - before, value=after)
                case SetStat(stat=stat, value=src):
                    after = self._set_stat(stat, self._int(src, where))
                    data.update(stat=stat, value=after)
                case GiveItem(item=key, qty=qty):
                    data.update(item=key, qty=self._give(key, qty))
                case TakeItem(item=key, qty=qty):
                    data.update(item=key, qty=self._take(key, qty))
                case EquipItem(item=key):
                    item = self._items.get(key)
                    if item and item.slot in self.tier.slots and self.state.items.get(key, 0) > 0:
                        self.state.equipped[item.slot] = key
                    data.update(item=key)
                case SetFlag(flag=f):
                    self.state.flags.add(f)
                    data.update(flag=f)
                case ClearFlag(flag=f):
                    self.state.flags.discard(f)
                    data.update(flag=f)
                case LearnSkill(skill=s):
                    self.state.skills.add(s)
                    data.update(skill=s)
                case ChooseClass(classes=wanted):
                    # Only a reader without a class picks one; otherwise nothing happens.
                    options = (
                        [k for k in self.tier.classes if not wanted or k in wanted]
                        if self.state.character_class is None
                        else []
                    )
                    if options:
                        self.state.class_pending = options
                    data.update(classes=options)
            self.log.append(Event("effect", data))
            xp_touched = xp_touched or (xp_key is not None and data.get("stat") == xp_key)
        if xp_touched:
            self._check_level_up()
        if check_defeat:
            self._check_defeat()

    def _check_defeat(self, *, in_combat: bool = False) -> None:
        if self.state.ended or (self.state.combat is not None and not in_combat):
            return
        for key, sd in self.tier.stats.items():
            if (
                sd.defeat_at is not None
                and "player" in sd.applies_to
                and self.state.stats.get(key, 0) <= sd.defeat_at
            ):
                self.state.combat = None
                self._end("defeated", None, f"{sd.label} reached {sd.defeat_at}")
                return

    def _end(self, kind: str, node: Node | None, reason: str | None = None) -> None:
        self.state.ended = kind
        self.state.ending_node_id = node.id if node else None
        data: dict[str, object] = {"ending": kind, "node": node.id if node else None}
        if reason:
            data["reason"] = reason
        self.log.append(Event("game_over", data))

    # ── movement ─────────────────────────────────────────────────────────

    def _enter(self, node: Node) -> None:
        s = self.state
        s.node_id = node.id
        s.visits[node.key] = s.visits.get(node.key, 0) + 1
        variant = None
        for v in sorted(node.variants, key=lambda v: -v.priority):
            if self._bool(v.condition, f"variant {v.label}"):
                variant = v
                break
        s.variant_id = variant.id if variant else None
        self.log.append(
            Event(
                "enter",
                {
                    "node": node.id,
                    "key": node.key,
                    "variant": s.variant_id,
                    "visit": s.visits[node.key],
                },
            )
        )
        # An authored ending takes precedence over stat defeat (its text is what
        # the reader sees), so only check defeat on non-ending nodes.
        self._apply(node.on_enter, f"enter:{node.id}", check_defeat=node.ending_kind is None)
        if s.ended:
            return
        if node.ending_kind is not None:
            self._end(node.ending_kind, node)
            return
        # Report broken choice conditions once, on arrival (queries stay silent).
        self._choices(log=True)
        self._check_stuck()

    def _check_stuck(self) -> None:
        """Stuck = nothing at all can be done (not even taking an item or shopping)."""
        if not self.state.ended and not self.available():
            self._end("stuck", self.node, "Nothing can be done here")

    def _go(self, choice: Choice, outcome_key: str) -> None:
        outcome = next((o for o in choice.outcomes if o.key == outcome_key), None)
        self.log.append(Event("outcome", {"choice": choice.id, "outcome": outcome_key}))
        target = self._nodes.get(outcome.target_id or "") if outcome else None
        if target is None:
            self._end(
                "stuck",
                self.node,
                f"Choice '{choice.label}' has no destination for '{outcome_key}'",
            )
            return
        self._enter(target)

    # ── actions ──────────────────────────────────────────────────────────

    def _choices(self, *, log: bool = False) -> list[tuple[Choice, bool]]:
        node = self.node
        if node is None:
            return []
        self._quiet = not log
        try:
            return self._choices_inner(node)
        finally:
            self._quiet = False

    def _choices_inner(self, node: Node) -> list[tuple[Choice, bool]]:
        out = []
        for c in node.choices:
            if not self.tier_allows(c.min_tier):
                continue
            ok = self._bool(c.condition, f"choice {c.label} condition")
            if ok or c.unmet_display == "show_disabled":
                out.append((c, ok))
        return out

    def actions(self) -> list[Action]:
        """Everything the reader could do now, including disabled options."""
        s = self.state
        if s.ended or self.node is None:
            return []
        out: list[Action] = []
        if s.class_pending:
            return [
                Action("choose_class", k, f"Become a {self.tier.classes[k].label}")
                for k in s.class_pending
            ]
        if s.combat is not None:
            out.append(Action("attack", None, "Attack"))
            if s.combat.flee_allowed:
                out.append(Action("flee", None, "Flee"))
            out += self._item_actions(in_combat=True)
            return out
        node = self.node
        for c, ok in self._choices():
            out.append(Action("choose", c.id, c.label, ok, None if ok else "Condition not met"))
        for i, p in enumerate(node.items):
            item = self._items_by_id.get(p.item_id)
            if item and f"take:{node.id}:{i}" not in s.fired:
                out.append(
                    Action(
                        "take", str(i), f"Take {item.name}" + (f" x{p.qty}" if p.qty > 1 else "")
                    )
                )
        if node.shop is not None:
            gold = s.stats.get(self.currency, 0) if self.currency else 0
            for i, entry in enumerate(node.shop):
                item = self._items_by_id.get(entry.item_id)
                if item is None:
                    continue
                stock = s.shop_stock.get(
                    f"{node.id}:{i}", entry.stock if entry.stock is not None else -1
                )
                reason = None
                if stock == 0:
                    reason = "Sold out"
                elif self.currency is None or gold < entry.price:
                    reason = "Not enough money"
                elif item.max_stack is not None and s.items.get(item.key, 0) >= item.max_stack:
                    reason = "Can't carry more"
                out.append(
                    Action(
                        "buy", str(i), f"Buy {item.name} ({entry.price})", reason is None, reason
                    )
                )
            if node.shop_sell_rate and self.currency is not None:
                for key, count in sorted(s.items.items()):
                    item = self._items.get(key)
                    if count > 0 and item and item.value > 0 and item.category != "key":
                        price = math.floor(item.value * node.shop_sell_rate / 100)
                        out.append(Action("sell", key, f"Sell {item.name} ({price})"))
        out += self._item_actions(in_combat=False)
        return out

    def _item_actions(self, *, in_combat: bool) -> list[Action]:
        s = self.state
        out: list[Action] = []
        for key, count in sorted(s.items.items()):
            item = self._items.get(key)
            if count <= 0 or item is None:
                continue
            if item.category == "consumable" and item.use_effects:
                out.append(Action("use", key, f"Use {item.name}"))
            if (
                not in_combat
                and item.slot
                and item.slot in self.tier.slots
                and s.equipped.get(item.slot) != key
            ):
                out.append(Action("equip", key, f"Equip {item.name}"))
        if not in_combat:
            for slot, key in sorted(s.equipped.items()):
                item = self._items.get(key)
                out.append(Action("unequip", slot, f"Unequip {item.name if item else key}"))
        return out

    def available(self) -> list[Action]:
        return [a for a in self.actions() if a.enabled]

    def step(self, action: Action) -> list[Event]:
        """Perform an action; returns the events it produced."""
        if self.state.ended:
            raise GameError("The game is over")
        if not any(a.key() == action.key() for a in self.available()):
            raise GameError(f"Action {action.type} {action.target or ''} is not available")
        mark = len(self.log)
        self.rng.history.clear()  # only this step's dice matter; keeps memory flat
        self.state.steps += 1
        self.log.append(Event("action", {"action": action.type, "target": action.target}))
        match action.type:
            case "choose":
                self._choose(action.target or "")
            case "attack":
                self._attack()
            case "flee":
                self._flee()
            case "take":
                self._take_found(int(action.target or 0))
            case "buy":
                self._buy(int(action.target or 0))
            case "sell":
                self._sell(action.target or "")
            case "use":
                self._use(action.target or "")
            case "equip":
                item = self._items[action.target or ""]
                assert item.slot is not None
                self.state.equipped[item.slot] = item.key
                self.log.append(Event("equipped", {"item": item.key, "slot": item.slot}))
            case "choose_class":
                self._pick_class(action.target or "")
            case "unequip":
                key = self.state.equipped.pop(action.target or "")
                self.log.append(Event("unequipped", {"item": key, "slot": action.target}))
        self._check_stuck()
        return self.log[mark:]

    def _choose(self, choice_id: str) -> None:
        node = self.node
        assert node is not None
        choice = next(c for c in node.choices if c.id == choice_id)
        self._apply(choice.effects, f"choice:{choice.id}")
        if self.state.ended:
            return
        match choice.kind:
            case "goto":
                self._go(choice, "default")
            case "roll":
                total = self._roll(choice.dice or "2d6", f"choice {choice.label}")
                hit = next(
                    (
                        o.key
                        for o in choice.outcomes
                        if o.range_lo is not None
                        and o.range_hi is not None
                        and o.range_lo <= total <= o.range_hi
                    ),
                    None,
                )
                if hit is None:
                    self._end("stuck", node, f"No outcome covers a roll of {total}")
                else:
                    self._go(choice, hit)
            case "test":
                self._test(choice)
            case "combat":
                self._start_combat(choice)

    def _test(self, choice: Choice) -> None:
        test = self.tier.tests.get(choice.test or "")
        if test is None:
            self._end("stuck", self.node, f"Unknown test {choice.test!r}")
            return
        total = self._roll(test.roll, f"test {test.key}")
        env = self._env.with_(variables={"roll": Fraction(total)})
        success = self._bool(test.success, f"test {test.key}", env)
        self.log.append(Event("test", {"test": test.key, "roll": total, "success": success}))
        self._apply(test.after, f"test:{test.key}", respect_once=False)
        if not self.state.ended:
            self._go(choice, "success" if success else "failure")

    def _pick_class(self, key: str) -> None:
        cls = self.tier.classes[key]
        self.state.class_pending = None
        self.state.character_class = cls.key
        self.state.skills.update(cls.skills)
        for b in cls.modifiers:
            self._bonus(b, f"class {cls.key} bonus")
        self.log.append(Event("class_chosen", {"class": cls.key}))
        self._starting_items(cls.starting_items)
        self._check_defeat()

    # ── combat ───────────────────────────────────────────────────────────

    def _encounter_enemies(self, enc: Encounter) -> list[Combatant] | None:
        """Enemies to fight, or None when a table roll produced something else."""
        enemy_stat_keys = self.tier.enemy_stats()
        enemies: list[tuple[str, int, int]] = []  # (enemy key, level, count)
        if enc.mode == "fixed":
            for ee in enc.enemies:
                enemy = self._enemies_by_id.get(ee.enemy_id)
                if enemy:
                    enemies.append((enemy.key, ee.level, ee.count))
        else:
            table = self._tables.get(enc.table_id or "")
            if table is None:
                return []
            total = self._roll(table.dice, f"table {table.key}")
            entry = next((e for e in table.entries if e.lo <= total <= e.hi), None)
            self.log.append(
                Event(
                    "table",
                    {"table": table.key, "roll": total, "result": entry.kind if entry else None},
                )
            )
            if entry is None or entry.kind == "nothing":
                return None
            if entry.kind == "item" and entry.item:
                self._give(entry.item, entry.qty)
                self.log.append(
                    Event(
                        "effect",
                        {
                            "source": f"table:{table.key}",
                            "op": "give",
                            "item": entry.item,
                            "qty": entry.qty,
                        },
                    )
                )
                return None
            if entry.kind == "gold":
                if self.currency:
                    amount = self._int(entry.amount or "0", f"table {table.key}")
                    self._set_stat(self.currency, self.state.stats.get(self.currency, 0) + amount)
                return None
            enemies = list(entry.enemies)
        out: list[Combatant] = []
        for key, level, count in enemies:
            enemy = self._enemies.get(key)
            if enemy is None:
                continue
            for n in range(count):
                out.append(
                    Combatant(
                        key=f"{key}#{n + 1}" if count > 1 else key,
                        name=enemy.name,
                        stats=enemy_stats(
                            enemy.stat_formulas, level, enemy_stat_keys, self.tiers, self.state.tier
                        ),
                        level=level,
                    )
                )
        return out

    def _start_combat(self, choice: Choice) -> None:
        node = self.node
        assert node is not None
        enc = next((e for e in node.encounters if e.id == choice.encounter_id), None)
        if enc is None:
            self._end("stuck", node, f"Choice '{choice.label}' has no encounter")
            return
        enemies = self._encounter_enemies(enc)
        if not enemies:
            self.log.append(Event("combat_skipped", {"encounter": enc.id}))
            self._go(choice, "win")
            return
        if self.combat_rules is None:
            self.log.append(Event("combat_unconfigured", {"encounter": enc.id}))
            self._go(choice, "win")
            return
        self.state.combat = CombatState(
            choice_id=choice.id,
            enemies=enemies,
            simultaneous=enc.fight == "simultaneous",
            flee_allowed=choice.flee_allowed and self.combat_rules.flee_allowed,
        )
        self.log.append(
            Event("combat_start", {"encounter": enc.id, "enemies": [e.to_dict() for e in enemies]})
        )

    def _finish_combat(self, outcome: str) -> None:
        cs = self.state.combat
        assert cs is not None
        self.state.combat = None
        self.log.append(Event("combat_end", {"outcome": outcome, "rounds": cs.round}))
        if outcome == "win":
            self._award_xp(cs.enemies)
        node = self.node
        assert node is not None
        choice = next(c for c in node.choices if c.id == cs.choice_id)
        self._go(choice, outcome)

    def _attack(self) -> None:
        cs = self.state.combat
        rules = self.combat_rules
        assert cs is not None
        assert rules is not None
        cs.round += 1
        player = self.effective_stats()
        before = player.get(rules.damage_stat, 0)
        try:
            self.log += fight_round(
                rules, self._env, self.rng, player, cs.enemies, cs.simultaneous, cs.round
            )
        except gbx.GbxEvalError as exc:
            self._error("combat", exc)
            self.state.combat = None
            self._end("stuck", self.node, f"Combat rules failed: {exc}")
            return
        delta = player.get(rules.damage_stat, 0) - before
        if delta:
            self._set_stat(rules.damage_stat, self.state.stats.get(rules.damage_stat, 0) + delta)
        # Damage lands on the base stat, so defeat is judged on the base stat too
        # (item bonuses don't make a reader unkillable).
        if player_defeated(rules, {rules.damage_stat: self.state.stats.get(rules.damage_stat, 0)}):
            self._finish_combat("lose")
        elif enemies_defeated(rules, cs.enemies):
            self._finish_combat("win")
        elif cs.round >= MAX_ROUNDS:
            self.log.append(Event("combat_stalemate", {"rounds": cs.round}))
            self._finish_combat("lose")

    def _flee(self) -> None:
        cs = self.state.combat
        assert cs is not None
        cost = self.tier.combat.flee_cost or []
        # Fleeing costs are applied while still "in combat" so they can't trigger
        # defeat before the flee outcome; the destination node decides what's next.
        self._apply(cost, "flee", respect_once=False)
        self._finish_combat("flee")
        self._check_defeat()

    # ── debug (the player's debug drawer; recorded like actions) ─────────

    def debug_jump(self, node_id: str) -> list[Event]:
        """Leave any fight and enter ``node_id`` as if a choice led there."""
        node = self._nodes.get(node_id)
        if node is None:
            raise GameError(f"Unknown node {node_id!r}")
        mark = len(self.log)
        self.state.combat = None
        self.state.ended = None
        self.state.ending_node_id = None
        self.log.append(Event("debug", {"op": "jump", "node": node_id}))
        self._enter(node)
        return self.log[mark:]

    def debug_set(
        self,
        *,
        stats: dict[str, int] | None = None,
        items: dict[str, int] | None = None,
        flags: dict[str, bool] | None = None,
    ) -> list[Event]:
        """Overwrite stats (clamped to their min/max), item counts and flags."""
        unknown = [k for k in stats or {} if k not in self.tier.stats]
        unknown += [k for k in items or {} if k not in self._items]
        if unknown:
            raise GameError(f"Unknown stat or item: {', '.join(sorted(unknown))}")
        mark = len(self.log)
        for key, value in (stats or {}).items():
            self._set_stat(key, value)
        for key, count in (items or {}).items():
            if count <= 0:
                self._take(key, self.state.items.get(key, 0))
            else:
                cap = self._items[key].max_stack
                self.state.items[key] = min(count, cap) if cap is not None else count
        for flag, on in (flags or {}).items():
            if on:
                self.state.flags.add(flag)
            else:
                self.state.flags.discard(flag)
        self.log.append(
            Event(
                "debug",
                {"op": "set", "stats": stats or {}, "items": items or {}, "flags": flags or {}},
            )
        )
        if self.state.combat is None and not self.state.ended:
            self._check_defeat()
        return self.log[mark:]

    def force_roll(self, total: int) -> list[Event]:
        """Make the next dice roll (not combat rounds) come out as ``total``."""
        self.forced_rolls.append(total)
        event = Event("debug", {"op": "force", "total": total})
        self.log.append(event)
        return [event]

    # ── items ────────────────────────────────────────────────────────────

    def _take_found(self, index: int) -> None:
        node = self.node
        assert node is not None
        p = node.items[index]
        item = self._items_by_id[p.item_id]
        self.state.fired.add(f"take:{node.id}:{index}")
        got = self._give(item.key, p.qty)
        self.log.append(Event("item_taken", {"item": item.key, "qty": got}))

    def _buy(self, index: int) -> None:
        node = self.node
        assert node is not None
        assert node.shop is not None
        assert self.currency is not None
        entry = node.shop[index]
        item = self._items_by_id[entry.item_id]
        key = f"{node.id}:{index}"
        if entry.stock is not None:
            self.state.shop_stock[key] = self.state.shop_stock.get(key, entry.stock) - 1
        self._set_stat(self.currency, self.state.stats.get(self.currency, 0) - entry.price)
        self._give(item.key, 1)
        self.log.append(Event("item_bought", {"item": item.key, "price": entry.price}))

    def _sell(self, key: str) -> None:
        node = self.node
        item = self._items[key]
        assert node is not None
        assert node.shop_sell_rate
        assert self.currency is not None
        price = math.floor(item.value * node.shop_sell_rate / 100)
        self._take(key, 1)
        self._set_stat(self.currency, self.state.stats.get(self.currency, 0) + price)
        self.log.append(Event("item_sold", {"item": key, "price": price}))

    def _use(self, key: str) -> None:
        item: Item = self._items[key]
        self._take(key, 1)
        self.log.append(Event("item_used", {"item": key}))
        self._apply(item.use_effects, f"use:{key}", respect_once=False)
        self._check_defeat(in_combat=True)
