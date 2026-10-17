import logging
import threading

from .exceptions import MissionNotFoundError
from .interfaces import MissionRepository
from .models import Mission

logger = logging.getLogger(__name__)


class InMemoryMissionRepository(MissionRepository):
    """Thread-safe in-memory storage for Missions."""
    
    def __init__(self):
        self._store: dict[str, Mission] = {}
        self._lock = threading.Lock()
        
    def save(self, mission: Mission) -> Mission:
        with self._lock:
            self._store[mission.mission_id.value] = mission
            return mission
            
    def get(self, mission_id: str) -> Mission:
        with self._lock:
            if mission_id not in self._store:
                raise MissionNotFoundError(f"Mission '{mission_id}' not found.")
            return self._store[mission_id]
            
    def list(self) -> list[Mission]:
        with self._lock:
            return list(self._store.values())
            
    def delete(self, mission_id: str) -> None:
        with self._lock:
            if mission_id not in self._store:
                raise MissionNotFoundError(f"Mission '{mission_id}' not found.")
            del self._store[mission_id]
            
    def exists(self, mission_id: str) -> bool:
        with self._lock:
            return mission_id in self._store


class SqliteMissionRepository(MissionRepository):
    """SQLite-backed persistent storage for Missions.
    Supports per-thread connections to avoid 'SQLite objects created in a thread
    can only be used in that same thread' errors across worker threads.
    """
    
    def __init__(self, connection) -> None:
        """
        Initialize with a sqlite3.Connection, connection factory callable, or db_path str/Path.
        Creates the table if it does not exist.
        """
        import sqlite3
        from pathlib import Path
        
        self._lock = threading.Lock()
        self._local = threading.local()
        self._connections_lock = threading.Lock()
        self._connections: dict[int, object] = {}
        self._factory = None
        self._db_path = None
        self._conn = None

        if isinstance(connection, (str, Path)):
            self._db_path = str(connection)
        elif callable(connection) and not isinstance(connection, sqlite3.Connection):
            self._factory = connection
        elif isinstance(connection, sqlite3.Connection):
            # Check if connection points to an on-disk database file
            try:
                cur = connection.cursor()
                cur.execute("PRAGMA database_list")
                rows = cur.fetchall()
                for row in rows:
                    if len(row) >= 3 and row[1] == "main" and row[2]:
                        self._db_path = str(row[2])
                        break
            except Exception as exc:  # noqa: BLE001 - fall back to the supplied connection
                logger.debug(
                    "Could not inspect SQLite connection database path (%s); using supplied connection",
                    type(exc).__name__,
                )
            if not self._db_path:
                self._conn = connection
        else:
            self._conn = connection

        self._ensure_table()

    def _get_conn(self):
        import sqlite3

        thread_id = threading.get_ident()
        local_conn = getattr(self._local, "conn", None)
        if local_conn is not None:
            with self._connections_lock:
                if self._connections.get(thread_id) is local_conn:
                    return local_conn
            # close() may have closed a connection owned by an exited worker;
            # don't hand that stale thread-local handle back out.
            del self._local.conn

        if self._db_path:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            with self._connections_lock:
                self._connections[thread_id] = conn
            return conn
        if self._factory:
            conn = self._factory()
            self._local.conn = conn
            with self._connections_lock:
                self._connections[thread_id] = conn
            return conn
        return self._conn

    def close(self) -> None:
        """Close owned SQLite handles, including path-backed worker connections.

        Path-backed connections are created with ``check_same_thread=False``, so
        the repository can close every registered handle even after its worker
        thread has exited. For caller-supplied factories, close only this thread's
        handle to respect factories that return thread-affine connections.
        """
        thread_id = threading.get_ident()
        with self._lock:
            with self._connections_lock:
                if self._db_path:
                    connections = list(self._connections.values())
                    self._connections.clear()
                else:
                    current = self._connections.pop(thread_id, None)
                    connections = [current] if current is not None else []

            local_conn = getattr(self._local, "conn", None)
            if local_conn is not None:
                del self._local.conn
            if self._conn is not None:
                connections.append(self._conn)
                self._conn = None

            seen: set[int] = set()
            for conn in connections:
                if conn is None or id(conn) in seen:
                    continue
                seen.add(id(conn))
                try:
                    conn.close()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Could not close SQLite connection (%s)", type(exc).__name__)

    def _ensure_table(self) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS missions (
                    mission_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
                '''
            )
            conn.commit()
            
    def save(self, mission: Mission) -> Mission:
        import json
        with self._lock:
            conn = self._get_conn()
            data_str = json.dumps(mission.to_dict())
            conn.execute(
                '''
                INSERT INTO missions (mission_id, data)
                VALUES (?, ?)
                ON CONFLICT(mission_id) DO UPDATE SET
                    data = excluded.data
                ''',
                (mission.mission_id.value, data_str)
            )
            conn.commit()
            return mission
            
    def get(self, mission_id: str) -> Mission:
        import json
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT data FROM missions WHERE mission_id = ?",
                (mission_id,)
            ).fetchone()
            
            if row is None:
                raise MissionNotFoundError(f"Mission '{mission_id}' not found.")
                
            data = json.loads(row[0] if isinstance(row, tuple) else row["data"])
            return Mission.from_dict(data)
            
    def list(self) -> list[Mission]:
        import json
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute("SELECT data FROM missions").fetchall()
            missions = []
            for row in rows:
                data = json.loads(row[0] if isinstance(row, tuple) else row["data"])
                missions.append(Mission.from_dict(data))
            return missions
            
    def delete(self, mission_id: str) -> None:
        with self._lock:
            conn = self._get_conn()
            # Check if exists first to raise error if not found
            row = conn.execute(
                "SELECT 1 FROM missions WHERE mission_id = ?",
                (mission_id,)
            ).fetchone()
            
            if row is None:
                raise MissionNotFoundError(f"Mission '{mission_id}' not found.")
                
            conn.execute(
                "DELETE FROM missions WHERE mission_id = ?",
                (mission_id,)
            )
            conn.commit()
            
    def exists(self, mission_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT 1 FROM missions WHERE mission_id = ?",
                (mission_id,)
            ).fetchone()
            return row is not None

