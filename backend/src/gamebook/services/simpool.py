"""Process pool for bot batches.

Bot games are pure CPU, so a batch fans out over worker processes. Workers
are started with ``spawn`` (safe inside a threaded web server) and kept alive;
each caches the books it has decoded by content hash.
"""

from __future__ import annotations

import multiprocessing
import os
import threading
from collections.abc import Iterator
from concurrent.futures import Executor, Future, ProcessPoolExecutor
from typing import Any

from gamebook.core.engine.bundle import from_bundle
from gamebook.core.model import BookSnapshot
from gamebook.core.sim import BotName, RunRecord, play_run

_lock = threading.Lock()
_pool: ProcessPoolExecutor | None = None
_pool_size = 0
_books: dict[str, BookSnapshot] = {}


def _book(content_hash: str, bundle: dict[str, Any]) -> BookSnapshot:
    book = _books.get(content_hash)
    if book is None:
        if len(_books) > 8:
            _books.clear()
        book = _books[content_hash] = from_bundle(bundle)
    return book


def run_chunk(
    content_hash: str,
    bundle: dict[str, Any],
    tier: str,
    bot: BotName,
    max_steps: int,
    jobs: list[tuple[int, int]],
) -> list[RunRecord]:
    """Play ``(index, seed)`` runs; executed in a worker process (or inline)."""
    book = _book(content_hash, bundle)
    return [play_run(book, tier, seed, bot, max_steps=max_steps, index=i) for i, seed in jobs]


def processes(setting: int) -> int:
    return setting if setting > 0 else max(1, os.cpu_count() or 1)


def _executor(n: int) -> Executor:
    global _pool, _pool_size
    with _lock:
        # A pool whose worker died (OOM, segfault) refuses all work: replace it.
        broken = _pool is not None and getattr(_pool, "_broken", False)
        if _pool is None or _pool_size != n or broken:
            if _pool is not None:
                _pool.shutdown(wait=False, cancel_futures=True)
            _pool = ProcessPoolExecutor(
                max_workers=n, mp_context=multiprocessing.get_context("spawn")
            )
            _pool_size = n
        return _pool


def run_batch(
    content_hash: str,
    bundle: dict[str, Any],
    tier: str,
    bot: BotName,
    max_steps: int,
    seeds: list[tuple[int, int]],
    *,
    workers: int,
    chunk: int = 200,
) -> Iterator[list[RunRecord]]:
    """Yield finished chunks of runs, in submission order."""
    chunks = [seeds[i : i + chunk] for i in range(0, len(seeds), chunk)]
    if workers <= 1:
        for c in chunks:
            yield run_chunk(content_hash, bundle, tier, bot, max_steps, c)
        return
    pool = _executor(workers)
    futures: list[Future[list[RunRecord]]] = [
        pool.submit(run_chunk, content_hash, bundle, tier, bot, max_steps, c) for c in chunks
    ]
    try:
        for f in futures:
            yield f.result()
    finally:
        for f in futures:
            f.cancel()


def shutdown() -> None:
    global _pool
    with _lock:
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
            _pool = None
