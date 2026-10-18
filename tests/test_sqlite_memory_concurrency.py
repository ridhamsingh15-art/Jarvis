from concurrent.futures import ThreadPoolExecutor

from memory.models import MemoryEntry
from memory.sqlite_memory import SqliteMemory


def test_sqlite_memory_enables_wal_and_busy_timeout(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    memory = SqliteMemory(str(db_path))

    conn = memory.get_connection()
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 10000
    finally:
        conn.close()


def test_connections_are_closed_after_memory_operations(tmp_path):
    memory = SqliteMemory(str(tmp_path / "memory.sqlite3"))
    memory.store(MemoryEntry(user_input="hello", summary="test"))

    second = SqliteMemory(str(tmp_path / "memory.sqlite3"))
    second.store(MemoryEntry(user_input="world", summary="test"))
    assert len(memory.get_recent(limit=10)) == 2


def test_concurrent_instances_serialize_writes(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    instances = [SqliteMemory(str(db_path)) for _ in range(4)]

    def write(index: int) -> None:
        instances[index % len(instances)].store(
            MemoryEntry(user_input=f"message-{index}", summary="concurrency")
        )

    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(write, range(120)))

    assert len(instances[0].get_recent(limit=200)) == 120


def test_fact_upserts_are_safe_across_instances(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    first = SqliteMemory(str(db_path))
    second = SqliteMemory(str(db_path))

    def upsert(index: int) -> None:
        (first if index % 2 else second).store_fact("key", str(index))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(upsert, range(80)))

    assert first.get_fact("key") is not None
    assert len(first.get_all_facts()) == 1
