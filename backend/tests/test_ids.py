import time
import uuid

from gamebook.ids import new_id, uuid7


def test_uuid7_version_and_variant() -> None:
    u = uuid7()
    assert u.version == 7
    assert u.variant == uuid.RFC_4122


def test_uuid7_embeds_current_millis() -> None:
    before = time.time_ns() // 1_000_000
    u = uuid7()
    after = time.time_ns() // 1_000_000
    assert before <= u.int >> 80 <= after + 1


def test_uuid7_strictly_increasing_and_unique() -> None:
    ids = [uuid7() for _ in range(20_000)]  # many per millisecond
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_new_id_is_canonical_string() -> None:
    s = new_id()
    assert len(s) == 36
    assert str(uuid.UUID(s)) == s
