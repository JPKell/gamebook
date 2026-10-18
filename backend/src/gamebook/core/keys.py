"""Human keys: stable handles used in expressions, exports and prompts.

Keys look like identifiers (``a1_bridge``, ``silver_key``, ``RAVEN``) so gbx can
reference them without quoting. By convention stats, flags and skills are
UPPER_CASE and entities are lower_snake_case, but only the pattern is enforced.
"""

import re

KEY_PATTERN = r"^[A-Za-z][A-Za-z0-9_]{0,63}$"
_KEY_RE = re.compile(KEY_PATTERN)
_DICE_RE = re.compile(r"^d\d+$")
_RESERVED = frozenset({"and", "or", "not", "true", "false", "tier", "player", "enemy"})


def key_problem(key: str) -> str | None:
    """Why ``key`` is invalid, or None if it's fine."""
    if not _KEY_RE.match(key):
        return "Keys start with a letter and use only letters, digits and _ (max 64)"
    if _DICE_RE.match(key):
        return "Keys can't look like dice (e.g. d6)"
    if key in _RESERVED:
        return f"{key!r} is reserved"
    return None


def slugify(text: str, fallback: str = "untitled") -> str:
    """Make a key from a title: 'The Haunted Bridge' → 'the_haunted_bridge'."""
    s = re.sub(r"[^A-Za-z0-9]+", "_", text.strip().lower()).strip("_")[:64]
    if not s or not s[0].isalpha():
        s = f"{fallback}_{s}".strip("_")[:64]
    if key_problem(s):
        s = f"{fallback}_{s}"[:64]
    return s


def unique_key(base: str, taken: set[str]) -> str:
    """``base``, or ``base_2``, ``base_3``… whichever is free."""
    if base not in taken:
        return base
    n = 2
    while f"{base[:60]}_{n}" in taken:
        n += 1
    return f"{base[:60]}_{n}"
