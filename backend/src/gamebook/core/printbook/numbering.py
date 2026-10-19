"""Section numbering: seeded shuffle within each act's range, pins, and a stable map.

Each act gets a consecutive block of numbers (act 1 first), so act openers can sit
before their act. Inside a block, sections are shuffled with the book's seed. Pins
are honoured when they fall inside their act's block. Numbers already assigned are
kept on re-export when they still fit, so adding a section doesn't renumber the
book; only an explicit reshuffle (a new seed, no previous map) does.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Numbering:
    numbers: dict[str, int]
    #: Pins that couldn't be honoured (outside their act's range, or taken twice).
    ignored_pins: dict[str, int]


def assign(
    acts: Sequence[Sequence[str]],
    *,
    seed: int,
    pins: Mapping[str, int],
    previous: Mapping[str, int],
) -> Numbering:
    """Numbers for section keys, given per act (in act order, each list in a stable order)."""
    numbers: dict[str, int] = {}
    ignored: dict[str, int] = {}
    start = 1
    for index, keys in enumerate(acts):
        lo, hi = start, start + len(keys) - 1
        start = hi + 1
        taken: set[int] = set()
        for key in keys:  # pins first
            n = pins.get(key)
            if n is None:
                continue
            if lo <= n <= hi and n not in taken:
                numbers[key] = n
                taken.add(n)
            else:
                ignored[key] = n
        for key in keys:  # then numbers from the last export that still fit
            if key in numbers:
                continue
            n = previous.get(key)
            if n is not None and lo <= n <= hi and n not in taken:
                numbers[key] = n
                taken.add(n)
        free = [n for n in range(lo, hi + 1) if n not in taken]
        rng = random.Random(f"{seed}:{index}")
        rng.shuffle(free)
        for key in keys:
            if key not in numbers:
                numbers[key] = free.pop()
    return Numbering(numbers, ignored)
