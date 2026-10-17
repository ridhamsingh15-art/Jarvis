"""Durable write-ahead journal for crash-safe mission execution.

This store is separate from the legacy mission checkpoint schema so every step
record includes a stable idempotency key and distinct OS/normalized exit codes.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class CrashSafeMissionStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS crash_missions (
                    mission_id TEXT PRIMARY KEY, objective TEXT NOT NULL,
                    state TEXT NOT NULL, failure_reason TEXT NOT NULL DEFAULT '', steps_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS crash_steps (
                    mission_id TEXT NOT NULL, step_index INTEGER NOT NULL,
                    tool TEXT NOT NULL, action TEXT NOT NULL, args_json TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL, side_effecting INTEGER NOT NULL,
                    status TEXT NOT NULL, stdout TEXT NOT NULL DEFAULT '',
                    stderr TEXT NOT NULL DEFAULT '', exit_code INTEGER,
                    normalized_code INTEGER, error TEXT NOT NULL DEFAULT '',
                    paths_json TEXT NOT NULL DEFAULT '[]', result_json TEXT NOT NULL DEFAULT 'null',
                    started_at TEXT NOT NULL DEFAULT '', finished_at TEXT NOT NULL DEFAULT '',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(mission_id, step_index),
                    FOREIGN KEY(mission_id) REFERENCES crash_missions(mission_id) ON DELETE CASCADE
                );
                """
            )
            columns = {row['name'] for row in db.execute('PRAGMA table_info(crash_missions)')}
            if 'steps_json' not in columns:
                db.execute("ALTER TABLE crash_missions ADD COLUMN steps_json TEXT NOT NULL DEFAULT '[]'")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15, isolation_level="IMMEDIATE")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def create_mission(self, mission_id: str, objective: str, steps: list[str] | None = None) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO crash_missions(mission_id, objective, state, failure_reason, steps_json) VALUES(?,?,?,?,?) "
                "ON CONFLICT(mission_id) DO NOTHING",
                (mission_id, objective, "RUNNING", "", json.dumps(steps or [], ensure_ascii=False)),
            )

    def set_mission_state(self, mission_id: str, state: str, reason: str = "") -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE crash_missions SET state=?, failure_reason=?, updated_at=CURRENT_TIMESTAMP WHERE mission_id=?",
                (state, reason, mission_id),
            )

    def mission(self, mission_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM crash_missions WHERE mission_id=?", (mission_id,)).fetchone()
            return dict(row) if row else None

    def step(self, mission_id: str, step_index: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM crash_steps WHERE mission_id=? AND step_index=?", (mission_id, step_index)
            ).fetchone()
            if not row:
                return None
            record = dict(row)
            record["args"] = json.loads(record.pop("args_json"))
            record["paths"] = json.loads(record.pop("paths_json"))
            record["result"] = json.loads(record.pop("result_json"))
            return record

    def begin_step(
        self, *, mission_id: str, step_index: int, tool: str, action: str,
        args: dict[str, Any], idempotency_key: str, side_effecting: bool,
        started_at: str,
    ) -> None:
        """Commit the write-ahead intent before any tool is invoked."""
        with self._connect() as db:
            db.execute(
                """INSERT INTO crash_steps(
                    mission_id, step_index, tool, action, args_json, idempotency_key,
                    side_effecting, status, started_at, attempt_count
                ) VALUES(?,?,?,?,?,?,?,?,?,1)
                ON CONFLICT(mission_id, step_index) DO UPDATE SET
                    tool=excluded.tool, action=excluded.action, args_json=excluded.args_json,
                    idempotency_key=excluded.idempotency_key, side_effecting=excluded.side_effecting,
                    status='started', stdout='', stderr='', exit_code=NULL, normalized_code=NULL,
                    error='', paths_json='[]', result_json='null', started_at=excluded.started_at,
                    finished_at='', attempt_count=crash_steps.attempt_count+1""",
                (mission_id, step_index, tool, action, json.dumps(args, ensure_ascii=False),
                 idempotency_key, int(side_effecting), "started", started_at),
            )
            db.execute(
                "UPDATE crash_missions SET state='RUNNING', failure_reason='', updated_at=CURRENT_TIMESTAMP WHERE mission_id=?",
                (mission_id,),
            )

    def finish_step(self, mission_id: str, step_index: int, record: dict[str, Any]) -> None:
        """Atomically persist result evidence and terminal status after execution."""
        with self._connect() as db:
            db.execute(
                """UPDATE crash_steps SET status=?, stdout=?, stderr=?, exit_code=?, normalized_code=?,
                   error=?, paths_json=?, result_json=?, finished_at=?
                   WHERE mission_id=? AND step_index=? AND status='started'""",
                (record["status"], record.get("stdout", ""), record.get("stderr", ""),
                 record.get("exit_code"), record.get("normalized_code"), record.get("error", ""),
                 json.dumps(record.get("paths", []), ensure_ascii=False),
                 json.dumps(record.get("result"), ensure_ascii=False, default=str),
                 record.get("finished_at", ""), mission_id, step_index),
            )
            if db.total_changes == 0:
                raise RuntimeError(f"WAL step {mission_id}/{step_index} was not in started state")

    def mark_needs_review(self, mission_id: str, step_index: int, reason: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE crash_steps SET status='needs_review', error=?, stderr=?, finished_at=CURRENT_TIMESTAMP "
                "WHERE mission_id=? AND step_index=? AND status='started'",
                (reason, reason, mission_id, step_index),
            )
            db.execute(
                "UPDATE crash_missions SET state='FAILED', failure_reason=?, updated_at=CURRENT_TIMESTAMP WHERE mission_id=?",
                (reason, mission_id),
            )


    def needs_review(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT m.mission_id, m.objective, m.state, m.failure_reason, m.updated_at,
                          s.step_index, s.tool, s.action, s.error AS review_reason
                   FROM crash_missions m JOIN crash_steps s ON s.mission_id=m.mission_id
                   WHERE s.status='needs_review' ORDER BY m.updated_at, m.mission_id, s.step_index"""
            ).fetchall()
            return [dict(row) for row in rows]

    def resolve_needs_review(self, mission_id: str, step_index: int, resolution: str) -> dict[str, Any]:
        if resolution not in {"retry", "abandon"}:
            raise ValueError("resolution must be 'retry' or 'abandon'")
        with self._connect() as db:
            row = db.execute(
                "SELECT error FROM crash_steps WHERE mission_id=? AND step_index=? AND status='needs_review'",
                (mission_id, step_index),
            ).fetchone()
            if row is None:
                raise ValueError(f"No needs_review step {step_index + 1} for mission {mission_id}")
            prior_reason = str(row["error"] or "unknown side-effect outcome")
            if resolution == "retry":
                db.execute(
                    "UPDATE crash_steps SET status='retry_authorized', stderr=?, finished_at='' WHERE mission_id=? AND step_index=?",
                    ("Operator explicitly authorized retry. Prior reason: " + prior_reason, mission_id, step_index),
                )
                db.execute(
                    "UPDATE crash_missions SET state='RUNNING', failure_reason='', updated_at=CURRENT_TIMESTAMP WHERE mission_id=?",
                    (mission_id,),
                )
            else:
                reason = "Abandoned by operator. Prior needs_review reason: " + prior_reason
                db.execute(
                    "UPDATE crash_steps SET status='abandoned', error=?, stderr=?, finished_at=CURRENT_TIMESTAMP WHERE mission_id=? AND step_index=?",
                    (reason, reason, mission_id, step_index),
                )
                db.execute(
                    "UPDATE crash_missions SET state='ABANDONED', failure_reason=?, updated_at=CURRENT_TIMESTAMP WHERE mission_id=?",
                    (reason, mission_id),
                )
        return self.mission(mission_id) or {}

    def steps(self, mission_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            indices = [row[0] for row in db.execute(
                "SELECT step_index FROM crash_steps WHERE mission_id=? ORDER BY step_index", (mission_id,)
            )]
        return [record for index in indices if (record := self.step(mission_id, index)) is not None]
