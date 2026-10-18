"""SQLite persistence for execution-backed mission checkpoints and step evidence."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .mission import Mission, MissionState, normalize_step_indexes


class MissionStoreCorruptionError(ValueError):
    """Raised when persisted mission JSON or state violates the storage contract."""


def _decode_json_column(raw: Any, column: str) -> Any:
    """Decode a persisted JSON column with a safe, field-specific error."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
        raise MissionStoreCorruptionError(
            f"Stored mission data is corrupt: {column} is not valid JSON."
        ) from exc


def _require_json_type(value: Any, expected_type: type, column: str) -> Any:
    if not isinstance(value, expected_type):
        raise MissionStoreCorruptionError(
            f"Stored mission data is corrupt: {column} has an invalid JSON type."
        )
    return value


def _decode_string_list(raw: Any, column: str) -> list[str]:
    value = _require_json_type(_decode_json_column(raw, column), list, column)
    if any(not isinstance(item, str) for item in value):
        raise MissionStoreCorruptionError(
            f"Stored mission data is corrupt: {column} must contain only strings."
        )
    return value


class MissionStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY, objective TEXT NOT NULL, state TEXT NOT NULL,
                    steps_json TEXT NOT NULL, completed_json TEXT NOT NULL,
                    pending_json TEXT NOT NULL, approved_json TEXT NOT NULL,
                    pending_approval_indexes_json TEXT NOT NULL DEFAULT '[]',
                    approved_step_indexes_json TEXT NOT NULL DEFAULT '[]',
                    failure_reason TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS mission_steps (
                    mission_id TEXT NOT NULL, step_index INTEGER NOT NULL, tool TEXT NOT NULL,
                    action TEXT NOT NULL, args_json TEXT NOT NULL, status TEXT NOT NULL,
                    stdout TEXT NOT NULL DEFAULT '', stderr TEXT NOT NULL DEFAULT '',
                    exit_code INTEGER, error TEXT NOT NULL DEFAULT '', paths_json TEXT NOT NULL DEFAULT '[]',
                    result_json TEXT NOT NULL DEFAULT 'null', started_at TEXT NOT NULL DEFAULT '',
                    finished_at TEXT NOT NULL DEFAULT '', PRIMARY KEY (mission_id, step_index),
                    FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE
                );
                """
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(missions)")}
            if "pending_approval_indexes_json" not in columns:
                db.execute("ALTER TABLE missions ADD COLUMN pending_approval_indexes_json TEXT NOT NULL DEFAULT '[]'")
            if "approved_step_indexes_json" not in columns:
                db.execute("ALTER TABLE missions ADD COLUMN approved_step_indexes_json TEXT NOT NULL DEFAULT '[]'")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 10000")
        db.execute("PRAGMA synchronous = FULL")
        return db

    @contextmanager
    def _connection(self):
        """Commit/rollback operations and always close the SQLite connection."""
        db = self._connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def save_mission(self, mission: Mission) -> None:
        with self._connection() as db:
            db.execute(
                """INSERT INTO missions(id, objective, state, steps_json, completed_json, pending_json,
                   approved_json, pending_approval_indexes_json, approved_step_indexes_json,
                   failure_reason, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                   ON CONFLICT(id) DO UPDATE SET objective=excluded.objective, state=excluded.state,
                   steps_json=excluded.steps_json, completed_json=excluded.completed_json,
                   pending_json=excluded.pending_json, approved_json=excluded.approved_json,
                   pending_approval_indexes_json=excluded.pending_approval_indexes_json,
                   approved_step_indexes_json=excluded.approved_step_indexes_json,
                   failure_reason=excluded.failure_reason, updated_at=CURRENT_TIMESTAMP""",
                (mission.id, mission.objective, mission.state.value, json.dumps(mission.steps),
                 json.dumps(mission.completed_steps), json.dumps(mission.pending_approvals),
                 json.dumps(mission.approved_steps), json.dumps(mission.pending_approval_indexes),
                 json.dumps(mission.approved_step_indexes), mission.failure_reason),
            )
            for item in mission.step_results:
                self._write_step(db, mission.id, int(item["step_index"]), item)

    def record_step(self, mission_id: str, step_index: int, record: dict[str, Any]) -> None:
        with self._connection() as db:
            self._write_step(db, mission_id, step_index, record)

    @staticmethod
    def _write_step(db: sqlite3.Connection, mission_id: str, step_index: int, record: dict[str, Any]) -> None:
        db.execute(
            """INSERT INTO mission_steps(mission_id, step_index, tool, action, args_json, status,
               stdout, stderr, exit_code, error, paths_json, result_json, started_at, finished_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(mission_id, step_index) DO UPDATE SET tool=excluded.tool, action=excluded.action,
               args_json=excluded.args_json, status=excluded.status, stdout=excluded.stdout,
               stderr=excluded.stderr, exit_code=excluded.exit_code, error=excluded.error,
               paths_json=excluded.paths_json, result_json=excluded.result_json,
               started_at=excluded.started_at, finished_at=excluded.finished_at""",
            (mission_id, step_index, str(record.get("tool", "")), str(record.get("action", "")),
             json.dumps(record.get("args", {}), ensure_ascii=False), str(record.get("status", "failed")),
             str(record.get("stdout", "")), str(record.get("stderr", "")), record.get("exit_code"),
             str(record.get("error", "")), json.dumps(record.get("paths", []), ensure_ascii=False),
             json.dumps(record.get("result"), ensure_ascii=False, default=str),
             str(record.get("started_at", "")), str(record.get("finished_at", ""))),
        )

    def load_mission(self, mission_id: str) -> Mission | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
            if row is None:
                return None

            steps = _decode_string_list(row["steps_json"], "missions.steps_json")
            completed = _decode_string_list(row["completed_json"], "missions.completed_json")
            pending = _decode_string_list(row["pending_json"], "missions.pending_json")
            approved = _decode_string_list(row["approved_json"], "missions.approved_json")
            pending_raw = _require_json_type(
                _decode_json_column(row["pending_approval_indexes_json"], "missions.pending_approval_indexes_json"),
                list,
                "missions.pending_approval_indexes_json",
            )
            approved_raw = _require_json_type(
                _decode_json_column(row["approved_step_indexes_json"], "missions.approved_step_indexes_json"),
                list,
                "missions.approved_step_indexes_json",
            )
            pending_indexes = normalize_step_indexes(pending_raw, len(steps))
            approved_indexes = normalize_step_indexes(approved_raw, len(steps))

            try:
                state = MissionState(row["state"])
            except (TypeError, ValueError) as exc:
                raise MissionStoreCorruptionError(
                    "Stored mission data is corrupt: missions.state is invalid."
                ) from exc

            for column in ("id", "objective", "failure_reason"):
                if not isinstance(row[column], str):
                    raise MissionStoreCorruptionError(
                        f"Stored mission data is corrupt: missions.{column} must be a string."
                    )

            results = []
            step_rows = db.execute(
                "SELECT * FROM mission_steps WHERE mission_id=? ORDER BY step_index",
                (mission_id,),
            )
            for step in step_rows:
                step_index = step["step_index"]
                if type(step_index) is not int or not 0 <= step_index < len(steps):
                    raise MissionStoreCorruptionError(
                        "Stored mission data is corrupt: mission_steps.step_index is out of range."
                    )
                for column in ("tool", "action", "status", "stdout", "stderr", "error", "started_at", "finished_at"):
                    if not isinstance(step[column], str):
                        raise MissionStoreCorruptionError(
                            f"Stored mission data is corrupt: mission_steps.{column} must be a string."
                        )
                args = _require_json_type(
                    _decode_json_column(step["args_json"], "mission_steps.args_json"),
                    dict,
                    "mission_steps.args_json",
                )
                paths = _require_json_type(
                    _decode_json_column(step["paths_json"], "mission_steps.paths_json"),
                    list,
                    "mission_steps.paths_json",
                )
                result = _decode_json_column(step["result_json"], "mission_steps.result_json")
                exit_code = step["exit_code"]
                if exit_code is not None and type(exit_code) is not int:
                    raise MissionStoreCorruptionError(
                        "Stored mission data is corrupt: mission_steps.exit_code must be an integer or null."
                    )
                results.append({
                    "step_index": step_index, "tool": step["tool"], "action": step["action"],
                    "args": args, "status": step["status"],
                    "stdout": step["stdout"], "stderr": step["stderr"], "exit_code": exit_code,
                    "error": step["error"], "paths": paths, "result": result,
                    "started_at": step["started_at"], "finished_at": step["finished_at"],
                })

            mission = Mission(
                id=row["id"], objective=row["objective"], state=state,
                steps=steps, completed_steps=completed,
                pending_approvals=pending, approved_steps=approved,
                pending_approval_indexes=pending_indexes,
                approved_step_indexes=approved_indexes,
                step_results=results, failure_reason=row["failure_reason"],
            )
            running = next((r for r in results if r["status"] == "running"), None)
            if running is not None:
                reason = (
                    f"Interrupted while step {running['step_index'] + 1} was running; "
                    "the outcome is unknown. Inspect the real-world result, then explicitly "
                    "resolve this step as completed or retry it."
                )
                mission.state = MissionState.RECOVERY_REQUIRED
                mission.failure_reason = reason
                running.update({"status": "unknown", "stderr": reason, "error": reason, "exit_code": 125})
                self.save_mission(mission)
            return mission

    def resolve_interrupted_step(self, mission_id: str, resolution: str) -> Mission:
        """Resolve an unknown step only after an explicit operator decision.

        `completed` records that the operator verified the side effect happened.
        `retry` authorizes re-execution after the operator checked it did not happen.
        Neither decision is inferred from model output.
        """
        if resolution not in {"completed", "retry"}:
            raise ValueError("resolution must be 'completed' or 'retry'")
        mission = self.load_mission(mission_id)
        if mission is None:
            raise ValueError(f"Mission not found: {mission_id}")
        if mission.state != MissionState.RECOVERY_REQUIRED:
            raise ValueError(f"Mission {mission_id} does not require interrupted-step recovery")
        unknown = [r for r in mission.step_results if r.get("status") == "unknown"]
        if len(unknown) != 1:
            raise ValueError(f"Expected exactly one unknown step; found {len(unknown)}")
        record = unknown[0]
        index = int(record["step_index"])
        step_text = mission.steps[index]
        if resolution == "completed":
            if step_text not in mission.completed_steps:
                mission.completed_steps.append(step_text)
            record.update({"status": "completed", "exit_code": 0, "error": "Operator confirmed the step's postcondition after interruption.", "stderr": "", "finished_at": datetime.now(timezone.utc).isoformat()})
            if len(mission.completed_steps) == len(mission.steps):
                mission.state = MissionState.COMPLETED
            else:
                mission.state = MissionState.RUNNING
        else:
            record.update({"status": "pending", "exit_code": None, "error": "Operator checked the postcondition and explicitly authorized retry.", "stderr": "", "started_at": "", "finished_at": ""})
            mission.state = MissionState.RUNNING
        mission.failure_reason = ""
        self.save_mission(mission)
        return mission

    def list_steps(self, mission_id: str) -> list[dict[str, Any]]:
        mission = self.load_mission(mission_id)
        return mission.step_results if mission else []
