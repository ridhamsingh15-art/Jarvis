from datetime import datetime, timedelta, timezone

from memory.models import MemoryEntry
from memory.sqlite_memory import SqliteMemory


def test_in_memory_database_survives_per_operation_connections_and_is_isolated():
    first = SqliteMemory(":memory:")
    first.store(MemoryEntry(user_input="in-memory conversation", summary="first"))
    first.store_fact("assistant", "JARVIS")

    assert [item.user_input for item in first.get_recent(limit=10)] == [
        "in-memory conversation"
    ]
    assert first.get_fact("assistant") == "JARVIS"

    # Each :memory: instance gets its own private database.
    second = SqliteMemory(":memory:")
    assert second.get_recent(limit=10) == []
    assert second.get_fact("assistant") is None


def test_timestamps_are_normalized_to_utc_before_persistence_and_sorting(tmp_path):
    memory = SqliteMemory(str(tmp_path / "timestamps.sqlite3"))
    earlier_local = datetime(
        2026, 10, 18, 12, 0, tzinfo=timezone(timedelta(hours=3))
    )  # 09:00 UTC
    later_utc = datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc)  # 10:00 UTC

    memory.store(MemoryEntry(user_input="earlier", timestamp=earlier_local))
    memory.store(MemoryEntry(user_input="later", timestamp=later_utc))

    recent = memory.get_recent(limit=10)
    assert [item.user_input for item in recent] == ["later", "earlier"]
    assert recent[0].timestamp == later_utc
    assert recent[1].timestamp == earlier_local.astimezone(timezone.utc)


def test_legacy_naive_timestamp_is_interpreted_as_utc(tmp_path):
    memory = SqliteMemory(str(tmp_path / "naive-timestamp.sqlite3"))
    naive = datetime(2026, 10, 18, 12, 30)  # noqa: DTZ001 - legacy naive timestamp test
    memory.store(MemoryEntry(user_input="legacy naive", timestamp=naive))

    restored = memory.get_recent(limit=1)[0]
    assert restored.timestamp == naive.replace(tzinfo=timezone.utc)
