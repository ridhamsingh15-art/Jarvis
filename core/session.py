"""
Session Architecture — Phase F implementation.

Minimum viable session model that reuses existing SQLite infrastructure.

Concepts:
    session_id      — uuid4, stable across resume
    conversation_id — links to memory/conversation store
    status          — active | ended | error

Does NOT duplicate memory. Session state references existing
SqliteMemory/MemoryManager infrastructure.

Operations:
    create()    — new session
    resume(id)  — load existing session
    end(id)     — mark complete
    get(id)     — retrieve metadata
    list_recent() — list sessions for resume picker

Storage: single SQLite table 'jarvis_sessions' in the existing DB.
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SessionStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"
    ERROR = "error"


@dataclass
class Session:
    session_id: str
    created_at: float
    updated_at: float
    status: SessionStatus
    conversation_id: str = ""
    metadata: dict[str, Any] | None = None

    def is_resumable(self) -> bool:
        return self.status == SessionStatus.ACTIVE


# ---------------------------------------------------------------------------
# SessionRepository — SQLite-backed
# ---------------------------------------------------------------------------


_SCHEMA = """
CREATE TABLE IF NOT EXISTS jarvis_sessions (
    session_id      TEXT PRIMARY KEY,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    conversation_id TEXT NOT NULL DEFAULT '',
    metadata        TEXT NOT NULL DEFAULT '{}'
);
"""


class SessionRepository:
    """
    SQLite-backed session store.

    Uses the same DB file as SqliteMemory. Accepts either:
    - a file path string
    - a connection factory callable () -> sqlite3.Connection

    Thread-safe: each call acquires its own connection when using a factory.
    """

    def __init__(self, db_path: str | None = None, connection_factory: Any = None) -> None:
        self._db_path = db_path
        self._factory = connection_factory
        # For in-memory mode (no file path, no factory), keep a single persistent
        # connection — each :memory: connection is isolated, so we must reuse one.
        self._mem_conn: sqlite3.Connection | None = None
        if db_path is None and connection_factory is None:
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.isolation_level = None  # autocommit for simplicity
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Public CRUD
    # ------------------------------------------------------------------

    def create(self, conversation_id: str = "", metadata: dict | None = None) -> Session:
        """Create a new session and persist it."""
        now = time.time()
        session = Session(
            session_id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            status=SessionStatus.ACTIVE,
            conversation_id=conversation_id,
            metadata=metadata or {},
        )
        self._execute(
            "INSERT INTO jarvis_sessions (session_id, created_at, updated_at, status, conversation_id, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session.session_id, session.created_at, session.updated_at,
             session.status.value, session.conversation_id,
             self._serialize_meta(session.metadata)),
        )
        logger.info("[SESSION] Created session_id=%s", session.session_id)
        return session

    def resume(self, session_id: str) -> Session | None:
        """Load an existing session. Returns None if not found."""
        rows = self._fetchall(
            "SELECT session_id, created_at, updated_at, status, conversation_id, metadata "
            "FROM jarvis_sessions WHERE session_id = ?",
            (session_id,),
        )
        if not rows:
            logger.warning("[SESSION] Session not found: %s", session_id)
            return None
        session = self._row_to_session(rows[0])
        # Update updated_at on resume
        self._execute(
            "UPDATE jarvis_sessions SET updated_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        logger.info("[SESSION] Resumed session_id=%s status=%s", session_id, session.status)
        return session

    def end(self, session_id: str) -> bool:
        """Mark a session as ended."""
        affected = self._execute(
            "UPDATE jarvis_sessions SET status = 'ended', updated_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        logger.info("[SESSION] Ended session_id=%s", session_id)
        return affected > 0

    def get(self, session_id: str) -> Session | None:
        """Get session metadata without updating updated_at."""
        rows = self._fetchall(
            "SELECT session_id, created_at, updated_at, status, conversation_id, metadata "
            "FROM jarvis_sessions WHERE session_id = ?",
            (session_id,),
        )
        return self._row_to_session(rows[0]) if rows else None

    def list_recent(self, limit: int = 10) -> list[Session]:
        """List most recently updated sessions."""
        rows = self._fetchall(
            "SELECT session_id, created_at, updated_at, status, conversation_id, metadata "
            "FROM jarvis_sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_session(r) for r in rows]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        try:
            conn = self._get_connection()
            conn.execute(_SCHEMA)
            conn.commit()
            if self._db_path:
                conn.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[SESSION] Schema creation failed: %s", exc)

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        if self._factory is not None:
            return self._factory()
        if self._db_path:
            return sqlite3.connect(self._db_path)
        # Fallback (should not reach here)
        return sqlite3.connect(":memory:")

    def _execute(self, sql: str, params: tuple = ()) -> int:
        """Execute a write statement. Returns number of affected rows."""
        try:
            conn = self._get_connection()
            cursor = conn.execute(sql, params)
            # Only commit if not using the persistent mem_conn (autocommit) or file-based
            if self._mem_conn is None:
                conn.commit()
            affected = cursor.rowcount
            if self._db_path and self._factory is None:
                conn.close()
            return affected
        except Exception as exc:  # noqa: BLE001
            logger.error("[SESSION] Execute failed: %s", exc)
            return 0

    def _fetchall(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Execute a read statement and return all rows."""
        try:
            conn = self._get_connection()
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            if self._db_path and self._factory is None:
                conn.close()
            return rows
        except Exception as exc:  # noqa: BLE001
            logger.error("[SESSION] Fetchall failed: %s", exc)
            return []

    @staticmethod
    def _serialize_meta(meta: dict | None) -> str:
        import json
        return json.dumps(meta or {})

    @staticmethod
    def _deserialize_meta(s: str) -> dict:
        import json
        try:
            return json.loads(s)
        except Exception:  # noqa: BLE001
            return {}

    def _row_to_session(self, row: tuple) -> Session:
        session_id, created_at, updated_at, status, conversation_id, metadata_str = row
        try:
            status_enum = SessionStatus(status)
        except ValueError:
            status_enum = SessionStatus.ERROR
        return Session(
            session_id=session_id,
            created_at=created_at,
            updated_at=updated_at,
            status=status_enum,
            conversation_id=conversation_id,
            metadata=self._deserialize_meta(metadata_str),
        )
