"""The simulation process pool recovers from a dead worker (review regression)."""

import os
from concurrent.futures.process import BrokenProcessPool

import pytest

from gamebook.core.engine.bundle import to_bundle
from gamebook.services import simpool

from .core.engine_book import engine_book


def test_broken_pool_is_replaced() -> None:
    bundle = to_bundle(engine_book())
    seeds = [(i, i) for i in range(4)]
    try:
        first = list(simpool.run_batch("h", bundle, "basic", "random", 50, seeds, workers=2))
        assert sum(len(c) for c in first) == 4
        pool = simpool._executor(2)
        with pytest.raises(BrokenProcessPool):
            pool.submit(os._exit, 1).result()
        again = list(simpool.run_batch("h", bundle, "basic", "random", 50, seeds, workers=2))
        assert [r.stored() for c in again for r in c] == [r.stored() for c in first for r in c]
    finally:
        simpool.shutdown()
