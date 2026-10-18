"""gbx Env adapters over game state and combatants."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache

from gamebook.core import gbx
from gamebook.core.gbx.compiler import compile_bool, compile_int
from gamebook.core.gbx.evaluator import Value
from gamebook.core.gbx.scope import RefKind


@lru_cache(maxsize=8192)
def compile_expr(src: str) -> gbx.Expr:
    """Parse once; ASTs are immutable so caching is safe."""
    return gbx.parse(src)


@lru_cache(maxsize=8192)
def compiled_int(src: str) -> Callable[[gbx.Env, gbx.Rng | None], int]:
    """Parse + compile once; raises GbxSyntaxError for bad source."""
    return compile_int(compile_expr(src))


@lru_cache(maxsize=8192)
def compiled_bool(src: str) -> Callable[[gbx.Env, gbx.Rng | None], bool]:
    return compile_bool(compile_expr(src))


class GameEnv:
    """Env for player-facing expressions (conditions, amounts, tests, combat)."""

    def __init__(
        self,
        tiers: Sequence[str],
        current_tier: str,
        player_stat: Callable[[str], int],
        ref: Callable[[str, str], int | bool],
        variables: Mapping[str, Value] | None = None,
        objects: Mapping[str, Mapping[str, int]] | None = None,
    ) -> None:
        self.tiers = tiers
        self.current_tier = current_tier
        self._player_stat = player_stat
        self._ref = ref
        self._variables = dict(variables or {})
        self._objects = dict(objects or {})

    def variable(self, name: str) -> Value | None:
        return self._variables.get(name)

    def stat(self, obj: str, key: str) -> int:
        if obj == "player" and "player" not in self._objects:
            return self._player_stat(key)
        return int(self._objects.get(obj, {}).get(key, 0))

    def ref(self, func: str, kind: RefKind, key: str) -> int | bool:
        return self._ref(func, key)

    def with_(
        self,
        variables: Mapping[str, Value] | None = None,
        objects: Mapping[str, Mapping[str, int]] | None = None,
    ) -> GameEnv:
        return GameEnv(
            self.tiers,
            self.current_tier,
            self._player_stat,
            self._ref,
            {**self._variables, **(variables or {})},
            {**self._objects, **(objects or {})},
        )


def no_refs(func: str, key: str) -> int | bool:
    return 0 if func in ("count", "visits") else False
