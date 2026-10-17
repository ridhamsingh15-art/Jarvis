"""
Session Architecture — Phase 7F implementation.

Persistent session and cross-turn continuity model that reuses existing SQLite infrastructure.

Concepts:
    session_id      — stable identifier across turns and restarts (e.g. sess_123)
    request_id      — unique per individual request (e.g. req_abc)
    status          — NEW | ACTIVE | IDLE | CLOSED | ENDED
    turns           — sequence of user/assistant interactions within the session

Storage:
    - jarvis_sessions table for session lifecycle metadata
    - jarvis_session_turns table for structured turn history
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SessionStatus(StrEnum):
    NEW = "new"
    ACTIVE = "active"
    IDLE = "idle"
    CLOSED = "closed"
    ENDED = "ended"  # backward compatibility alias
    ERROR = "error"


@dataclass
class SessionTurn:
    """A single conversational or task turn within a persistent session."""

    turn_id: str
    session_id: str
    turn_index: int
    request_id: str
    user_input: str
    response: str
    route: str
    tools_executed: list[dict[str, Any]] = field(default_factory=list)
    target_files: list[str] = field(default_factory=list)
    mission_state: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "turn_index": self.turn_index,
            "request_id": self.request_id,
            "user_input": self.user_input,
            "response": self.response,
            "route": self.route,
            "tools_executed": self.tools_executed,
            "target_files": self.target_files,
            "mission_state": self.mission_state,
            "created_at": self.created_at,
        }


@dataclass
class Session:
    """Persistent session containing lifecycle status, metadata, and turn history."""

    session_id: str
    created_at: float
    updated_at: float
    status: SessionStatus
    conversation_id: str = ""
    metadata: dict[str, Any] | None = None
    turns: list[SessionTurn] = field(default_factory=list)

    def is_resumable(self) -> bool:
        return self.status in (SessionStatus.NEW, SessionStatus.ACTIVE, SessionStatus.IDLE)

    def is_closed(self) -> bool:
        return self.status in (SessionStatus.CLOSED, SessionStatus.ENDED)

    def get_recent_conversation(self, limit: int = 5) -> list[dict[str, str]]:
        """Return recent user/assistant turns in role-content dict format."""
        recent = self.turns[-limit:] if self.turns else []
        msgs: list[dict[str, str]] = []
        for t in recent:
            msgs.append({"role": "user", "content": t.user_input})
            if t.response:
                msgs.append({"role": "assistant", "content": t.response})
        return msgs

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def last_target_file(self) -> str | None:
        meta = self.metadata or {}
        if meta.get("last_target_file"):
            return str(meta["last_target_file"])
        for t in reversed(self.turns):
            if t.target_files:
                return t.target_files[-1]
        return None

    @property
    def last_target_content(self) -> str | None:
        meta = self.metadata or {}
        return meta.get("last_target_content")

    @property
    def active_mission(self) -> dict[str, Any] | None:
        meta = self.metadata or {}
        if meta.get("active_mission"):
            return meta["active_mission"]
        for t in reversed(self.turns):
            if t.mission_state:
                return t.mission_state
        return None


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

CREATE TABLE IF NOT EXISTS jarvis_session_turns (
    turn_id         TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    turn_index      INTEGER NOT NULL,
    request_id      TEXT NOT NULL,
    user_input      TEXT NOT NULL,
    response        TEXT NOT NULL,
    route           TEXT NOT NULL,
    tools_executed  TEXT NOT NULL DEFAULT '[]',
    target_files    TEXT NOT NULL DEFAULT '[]',
    mission_state   TEXT NOT NULL DEFAULT '{}',
    created_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_session_turns ON jarvis_session_turns(session_id, turn_index);
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
        self._mem_conn: sqlite3.Connection | None = None
        if db_path is None and connection_factory is None:
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.isolation_level = None  # autocommit for memory
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Public CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        session_id: str | None = None,
        conversation_id: str = "",
        metadata: dict | None = None,
    ) -> Session:
        """Create a new session and persist it. If session_id already exists, load and return it."""
        sid = session_id or str(uuid.uuid4())
        existing = self.get(sid)
        if existing is not None:
            return existing

        now = time.time()
        session = Session(
            session_id=sid,
            created_at=now,
            updated_at=now,
            status=SessionStatus.ACTIVE,
            conversation_id=conversation_id,
            metadata=metadata or {},
            turns=[],
        )
        self._execute(
            "INSERT INTO jarvis_sessions (session_id, created_at, updated_at, status, conversation_id, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                session.session_id,
                session.created_at,
                session.updated_at,
                session.status.value,
                session.conversation_id,
                self._serialize_json(session.metadata),
            ),
        )
        logger.info("[SESSION] Created session_id=%s", session.session_id)
        return session

    def resume(self, session_id: str) -> Session | None:
        """Load an existing session and all associated turns. Returns None if not found."""
        session = self.get(session_id)
        if session is None:
            logger.warning("[SESSION] Session not found: %s", session_id)
            return None

        # Update updated_at and reactivate if IDLE or NEW
        new_status = SessionStatus.ACTIVE if session.status in (SessionStatus.IDLE, SessionStatus.NEW) else session.status
        self._execute(
            "UPDATE jarvis_sessions SET updated_at = ?, status = ? WHERE session_id = ?",
            (time.time(), new_status.value, session_id),
        )
        session.updated_at = time.time()
        session.status = new_status
        logger.info("[SESSION] Resumed session_id=%s status=%s turns=%d", session_id, session.status, len(session.turns))
        return session

    def get(self, session_id: str) -> Session | None:
        """Get session metadata and turns without updating updated_at."""
        rows = self._fetchall(
            "SELECT session_id, created_at, updated_at, status, conversation_id, metadata "
            "FROM jarvis_sessions WHERE session_id = ?",
            (session_id,),
        )
        if not rows:
            return None

        session = self._row_to_session(rows[0])
        session.turns = self.get_turns(session_id)
        return session

    get_session = get

    def end(self, session_id: str) -> bool:
        """Mark a session as ended (backward compat)."""
        affected = self._execute(
            "UPDATE jarvis_sessions SET status = 'ended', updated_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        logger.info("[SESSION] Ended session_id=%s", session_id)
        return affected > 0

    def close(self, session_id: str) -> bool:
        """Mark a session as closed."""
        affected = self._execute(
            "UPDATE jarvis_sessions SET status = 'closed', updated_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        logger.info("[SESSION] Closed session_id=%s", session_id)
        return affected > 0

    def mark_idle(self, session_id: str) -> bool:
        """Mark an active session as idle."""
        affected = self._execute(
            "UPDATE jarvis_sessions SET status = 'idle', updated_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        return affected > 0

    def add_turn(
        self,
        session_id: str,
        request_id: str,
        user_input: str,
        response: str,
        route: str,
        tools_executed: list[dict[str, Any]] | None = None,
        target_files: list[str] | None = None,
        mission_state: dict[str, Any] | None = None,
        metadata_updates: dict[str, Any] | None = None,
    ) -> SessionTurn:
        """Append an interaction turn to the session.

        Raises:
            ValueError: If session does not exist or is closed/ended.
        """
        session = self.get(session_id)
        if session is None:
            raise ValueError(f"Cannot add turn to nonexistent session: {session_id}")
        if session.is_closed():
            raise ValueError(f"Cannot mutate closed session: {session_id}")

        turn_index = len(session.turns) + 1
        turn_id = f"turn_{turn_index}_{uuid.uuid4().hex[:4]}"
        now = time.time()

        turn = SessionTurn(
            turn_id=turn_id,
            session_id=session_id,
            turn_index=turn_index,
            request_id=request_id,
            user_input=user_input,
            response=response,
            route=route,
            tools_executed=tools_executed or [],
            target_files=target_files or [],
            mission_state=mission_state or {},
            created_at=now,
        )

        self._execute(
            "INSERT INTO jarvis_session_turns ("
            "turn_id, session_id, turn_index, request_id, user_input, response, route, "
            "tools_executed, target_files, mission_state, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                turn.turn_id,
                turn.session_id,
                turn.turn_index,
                turn.request_id,
                turn.user_input,
                turn.response,
                turn.route,
                self._serialize_json(turn.tools_executed),
                self._serialize_json(turn.target_files),
                self._serialize_json(turn.mission_state),
                turn.created_at,
            ),
        )

        # Update session metadata
        meta = session.metadata or {}
        meta["turn_count"] = turn_index
        meta["last_activity"] = now
        meta["last_route"] = route
        if target_files:
            meta["last_target_file"] = target_files[-1]
        if metadata_updates:
            meta.update(metadata_updates)
        if mission_state:
            meta["active_mission"] = mission_state

        self._execute(
            "UPDATE jarvis_sessions SET updated_at = ?, metadata = ? WHERE session_id = ?",
            (now, self._serialize_json(meta), session_id),
        )
        return turn

    def get_turns(self, session_id: str, limit: int = 50) -> list[SessionTurn]:
        """Retrieve turns for a session in chronological order."""
        rows = self._fetchall(
            "SELECT turn_id, session_id, turn_index, request_id, user_input, response, route, "
            "tools_executed, target_files, mission_state, created_at "
            "FROM jarvis_session_turns WHERE session_id = ? "
            "ORDER BY turn_index ASC LIMIT ?",
            (session_id, limit),
        )
        return [self._row_to_turn(r) for r in rows]

    def cleanup_expired(self, max_age_seconds: float) -> int:
        """Close sessions that have been idle longer than max_age_seconds."""
        threshold = time.time() - max_age_seconds
        affected = self._execute(
            "UPDATE jarvis_sessions SET status = 'closed', updated_at = ? "
            "WHERE updated_at < ? AND status NOT IN ('closed', 'ended')",
            (time.time(), threshold),
        )
        logger.info("[SESSION] Cleaned up %d expired sessions (threshold=%.1fs)", affected, max_age_seconds)
        return affected

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
            conn.executescript(_SCHEMA)
            conn.commit()
            if self._db_path and self._factory is None:
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
        return sqlite3.connect(":memory:")

    def _execute(self, sql: str, params: tuple = ()) -> int:
        """Execute a write statement. Returns number of affected rows."""
        try:
            conn = self._get_connection()
            cursor = conn.execute(sql, params)
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
    def _serialize_json(data: Any) -> str:
        return json.dumps(data if data is not None else {})

    @staticmethod
    def _deserialize_json(s: str) -> Any:
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
            metadata=self._deserialize_json(metadata_str),
        )

    def _row_to_turn(self, row: tuple) -> SessionTurn:
        (
            turn_id,
            session_id,
            turn_index,
            request_id,
            user_input,
            response,
            route,
            tools_json,
            files_json,
            mission_json,
            created_at,
        ) = row
        return SessionTurn(
            turn_id=turn_id,
            session_id=session_id,
            turn_index=turn_index,
            request_id=request_id,
            user_input=user_input,
            response=response,
            route=route,
            tools_executed=self._deserialize_json(tools_json) or [],
            target_files=self._deserialize_json(files_json) or [],
            mission_state=self._deserialize_json(mission_json) or {},
            created_at=created_at,
        )
