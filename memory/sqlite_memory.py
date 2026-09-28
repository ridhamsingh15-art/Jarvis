"""
SQLite-backed memory storage for Jarvis.

Persists conversation history to a local SQLite database file.
Requires zero infrastructure — uses Python's built-in sqlite3
module. The database and table are auto-created on first use.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.exceptions import MemoryError
from memory.base_memory import BaseMemory
from memory.models import MemoryEntry

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS memory (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    user_input TEXT NOT NULL,
    tasks_json TEXT NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL DEFAULT ''
)
"""

_CREATE_FACTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS memory_facts (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_INSERT_SQL = """
INSERT INTO memory (id, timestamp, user_input, tasks_json, summary)
VALUES (?, ?, ?, ?, ?)
"""

_SELECT_RECENT_SQL = """
SELECT id, timestamp, user_input, tasks_json, summary
FROM memory
ORDER BY timestamp DESC
LIMIT ?
"""

_SEARCH_SQL = """
SELECT id, timestamp, user_input, tasks_json, summary
FROM memory
WHERE user_input LIKE ? OR summary LIKE ?
ORDER BY timestamp DESC
LIMIT ?
"""

_DELETE_ALL_SQL = "DELETE FROM memory"
_DELETE_ALL_FACTS_SQL = "DELETE FROM memory_facts"


class SqliteMemory(BaseMemory):
    """SQLite implementation of the Jarvis memory backend.

    Creates the database file and table automatically on
    first instantiation. All operations are transactional.
    """

    def __init__(self, db_path: str) -> None:
        """Initialize the SQLite memory backend.

        Args:
            db_path: Path to the SQLite database file.
                Parent directories are created if needed.
        """
        self._db_path = db_path
        self._ensure_database()

    def _ensure_database(self) -> None:
        """Create the database file and table if they don't exist."""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

            with self._connect() as conn:
                conn.execute(_CREATE_TABLE_SQL)
                conn.execute(_CREATE_FACTS_TABLE_SQL)

            logger.info("Memory database ready: %s", self._db_path)
        except sqlite3.Error as exc:
            raise MemoryError(f"Failed to initialize memory database: {exc}") from exc

    def _connect(self) -> sqlite3.Connection:
        """Create a new database connection.

        Returns:
            sqlite3.Connection with row factory enabled.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_connection(self) -> sqlite3.Connection:
        """Returns a new sqlite3 Connection."""
        return self._connect()

    def store(self, entry: MemoryEntry) -> None:
        """Persist a memory entry to SQLite.

        Args:
            entry: The MemoryEntry to store.

        Raises:
            MemoryError: If the insert fails.
        """
        try:
            tasks_json = json.dumps(entry.tasks, default=str)

            with self._connect() as conn:
                conn.execute(
                    _INSERT_SQL,
                    (
                        entry.id,
                        entry.timestamp.isoformat(),
                        entry.user_input,
                        tasks_json,
                        entry.summary,
                    ),
                )

            logger.debug("Stored memory entry: %s", entry.id)
        except sqlite3.Error as exc:
            raise MemoryError(f"Failed to store memory entry: {exc}") from exc

    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Retrieve the most recent memory entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of MemoryEntry objects, most recent first.
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(_SELECT_RECENT_SQL, (limit,)).fetchall()

            return [self._row_to_entry(row) for row in rows]
        except sqlite3.Error as exc:
            logger.error("Failed to retrieve recent memories: %s", exc)
            return []

    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Search memory entries by keyword using SQL LIKE.

        Args:
            query: Search term to match against user input and summary.
            limit: Maximum number of results.

        Returns:
            List of matching MemoryEntry objects.
        """
        try:
            pattern = f"%{query}%"

            with self._connect() as conn:
                rows = conn.execute(_SEARCH_SQL, (pattern, pattern, limit)).fetchall()

            return [self._row_to_entry(row) for row in rows]
        except sqlite3.Error as exc:
            logger.error("Memory search failed: %s", exc)
            return []

    def clear(self) -> None:
        """Delete all memory entries.

        Raises:
            MemoryError: If the clear operation fails.
        """
        try:
            with self._connect() as conn:
                conn.execute(_DELETE_ALL_SQL)
                conn.execute(_DELETE_ALL_FACTS_SQL)

            logger.info("Memory cleared")
        except sqlite3.Error as exc:
            raise MemoryError(f"Failed to clear memory: {exc}") from exc

    def store_fact(self, key: str, value: str) -> None:
        """Store or replace a user fact using a stable, normalized key."""
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO memory_facts (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, value, datetime.now(timezone.utc).isoformat()),
                )
        except sqlite3.Error as exc:
            raise MemoryError(f"Failed to store fact: {exc}") from exc

    def get_fact(self, key: str) -> str | None:
        """Return a stored user fact, if present."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT value FROM memory_facts WHERE key = ?", (key,)
                ).fetchone()
            return str(row["value"]) if row is not None else None
        except sqlite3.Error as exc:
            raise MemoryError(f"Failed to retrieve fact: {exc}") from exc

    def get_all_facts(self) -> dict[str, str]:
        """Return all stored user facts."""
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT key, value FROM memory_facts").fetchall()
            return {str(row["key"]): str(row["value"]) for row in rows}
        except sqlite3.Error as exc:
            raise MemoryError(f"Failed to retrieve facts: {exc}") from exc

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        """Convert a database row to a MemoryEntry.

        Args:
            row: A sqlite3.Row from the memory table.

        Returns:
            Reconstructed MemoryEntry instance.
        """
        return MemoryEntry(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]).replace(
                tzinfo=timezone.utc
            ),
            user_input=row["user_input"],
            tasks=json.loads(row["tasks_json"]),
            summary=row["summary"],
        )
