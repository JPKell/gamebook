"""Graph helpers over a BookSnapshot (conditions ignored: may-reachability)."""

from collections import deque
from collections.abc import Iterable

from gamebook.core.model import BookSnapshot


def successors(book: BookSnapshot) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {n.id: set() for n in book.nodes}
    for n in book.nodes:
        for c in n.choices:
            for o in c.outcomes:
                if o.target_id is not None and o.target_id in out:
                    out[n.id].add(o.target_id)
    return out


def reachable(adjacency: dict[str, set[str]], roots: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    queue = deque(r for r in roots if r in adjacency)
    seen.update(queue)
    while queue:
        for nxt in adjacency[queue.popleft()]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def reverse(adjacency: dict[str, set[str]]) -> dict[str, set[str]]:
    rev: dict[str, set[str]] = {k: set() for k in adjacency}
    for src, targets in adjacency.items():
        for t in targets:
            rev[t].add(src)
    return rev
