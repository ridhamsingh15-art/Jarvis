"""SQLite persistence for execution-backed mission checkpoints and step evidence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .mission import Mission, MissionState


class MissionStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY, objective TEXT NOT NULL, state TEXT NOT NULL,
                    steps_json TEXT NOT NULL, completed_json TEXT NOT NULL,
                    pending_json TEXT NOT NULL, approved_json TEXT NOT NULL,
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

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def save_mission(self, mission: Mission) -> None:
        with self._connect() as db:
            db.execute(
                """INSERT INTO missions(id, objective, state, steps_json, completed_json, pending_json,
                   approved_json, failure_reason, updated_at) VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                   ON CONFLICT(id) DO UPDATE SET objective=excluded.objective, state=excluded.state,
                   steps_json=excluded.steps_json, completed_json=excluded.completed_json,
                   pending_json=excluded.pending_json, approved_json=excluded.approved_json,
                   failure_reason=excluded.failure_reason, updated_at=CURRENT_TIMESTAMP""",
                (mission.id, mission.objective, mission.state.value, json.dumps(mission.steps),
                 json.dumps(mission.completed_steps), json.dumps(mission.pending_approvals),
                 json.dumps(mission.approved_steps), mission.failure_reason),
            )
            for item in mission.step_results:
                self._write_step(db, mission.id, int(item["step_index"]), item)

    def record_step(self, mission_id: str, step_index: int, record: dict[str, Any]) -> None:
        with self._connect() as db:
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
        with self._connect() as db:
            row = db.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
            if row is None:
                return None
            results = []
            for step in db.execute("SELECT * FROM mission_steps WHERE mission_id=? ORDER BY step_index", (mission_id,)):
                results.append({
                    "step_index": step["step_index"], "tool": step["tool"], "action": step["action"],
                    "args": json.loads(step["args_json"]), "status": step["status"],
                    "stdout": step["stdout"], "stderr": step["stderr"], "exit_code": step["exit_code"],
                    "error": step["error"], "paths": json.loads(step["paths_json"]),
                    "result": json.loads(step["result_json"]), "started_at": step["started_at"],
                    "finished_at": step["finished_at"],
                })
            mission = Mission(
                id=row["id"], objective=row["objective"], state=MissionState(row["state"]),
                steps=json.loads(row["steps_json"]), completed_steps=json.loads(row["completed_json"]),
                pending_approvals=json.loads(row["pending_json"]), approved_steps=json.loads(row["approved_json"]),
                step_results=results, failure_reason=row["failure_reason"],
            )
            running = next((r for r in results if r["status"] == "running"), None)
            if running is not None:
                reason = (
                    f"Interrupted while step {running['step_index'] + 1} was running; "
                    "the outcome is unknown, so it was not replayed automatically."
                )
                mission.state = MissionState.FAILED
                mission.failure_reason = reason
                running.update({"status": "failed", "stderr": reason, "error": reason, "exit_code": 125})
                self.save_mission(mission)
            return mission

    def list_steps(self, mission_id: str) -> list[dict[str, Any]]:
        mission = self.load_mission(mission_id)
        return mission.step_results if mission else []
