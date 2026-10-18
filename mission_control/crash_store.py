"""Durable write-ahead journal for crash-safe mission execution.

This store is separate from the legacy mission checkpoint schema so every step
record includes a stable idempotency key and distinct OS/normalized exit codes.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class CrashSafeStoreCorruptionError(ValueError):
    """Raised when persisted crash-safe mission state violates its storage contract."""


def _decode_json(raw: Any, column: str) -> Any:
    """Decode a crash-store JSON column without leaking raw decoder failures."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
        raise CrashSafeStoreCorruptionError(
            f"Stored crash-safe mission data is corrupt: {column} is not valid JSON."
        ) from exc


def _require_json_type(value: Any, expected_type: type, column: str) -> Any:
    if not isinstance(value, expected_type):
        raise CrashSafeStoreCorruptionError(
            f"Stored crash-safe mission data is corrupt: {column} has an invalid JSON type."
        )
    return value


class CrashSafeMissionStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
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
                    verification_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL DEFAULT '', finished_at TEXT NOT NULL DEFAULT '',
                    attempt_count INTEGER NOT NULL DEFAULT 0, runner_pid INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(mission_id, step_index),
                    FOREIGN KEY(mission_id) REFERENCES crash_missions(mission_id) ON DELETE CASCADE
                );
                """
            )
            columns = {row['name'] for row in db.execute('PRAGMA table_info(crash_missions)')}
            if 'steps_json' not in columns:
                db.execute("ALTER TABLE crash_missions ADD COLUMN steps_json TEXT NOT NULL DEFAULT '[]'")
            step_columns = {row['name'] for row in db.execute('PRAGMA table_info(crash_steps)')}
            if 'verification_json' not in step_columns:
                db.execute("ALTER TABLE crash_steps ADD COLUMN verification_json TEXT NOT NULL DEFAULT '{}'")
            if 'runner_pid' not in step_columns:
                db.execute("ALTER TABLE crash_steps ADD COLUMN runner_pid INTEGER NOT NULL DEFAULT 0")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15, isolation_level="IMMEDIATE")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        return db

    @contextmanager
    def _connection(self):
        """Commit/rollback and always close path-backed SQLite connections."""
        db = self._connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_mission(self, mission_id: str, objective: str, steps: list[str] | None = None) -> None:
        with self._connection() as db:
            db.execute(
                "INSERT INTO crash_missions(mission_id, objective, state, failure_reason, steps_json) VALUES(?,?,?,?,?) "
                "ON CONFLICT(mission_id) DO NOTHING",
                (mission_id, objective, "RUNNING", "", json.dumps(steps or [], ensure_ascii=False)),
            )

    def set_mission_state(self, mission_id: str, state: str, reason: str = "") -> None:
        with self._connection() as db:
            db.execute(
                "UPDATE crash_missions SET state=?, failure_reason=?, updated_at=CURRENT_TIMESTAMP WHERE mission_id=?",
                (state, reason, mission_id),
            )

    def mission(self, mission_id: str) -> dict[str, Any] | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM crash_missions WHERE mission_id=?", (mission_id,)).fetchone()
            return dict(row) if row else None

    def step(self, mission_id: str, step_index: int) -> dict[str, Any] | None:
        with self._connection() as db:
            row = db.execute(
                "SELECT * FROM crash_steps WHERE mission_id=? AND step_index=?", (mission_id, step_index)
            ).fetchone()
            if not row:
                return None
            record = dict(row)
            record["args"] = _require_json_type(
                _decode_json(record.pop("args_json"), "crash_steps.args_json"),
                dict,
                "crash_steps.args_json",
            )
            record["paths"] = _require_json_type(
                _decode_json(record.pop("paths_json"), "crash_steps.paths_json"),
                list,
                "crash_steps.paths_json",
            )
            record["result"] = _decode_json(record.pop("result_json"), "crash_steps.result_json")
            record["verification"] = _require_json_type(
                _decode_json(record.pop("verification_json", "{}"), "crash_steps.verification_json"),
                dict,
                "crash_steps.verification_json",
            )
            return record

    def begin_step(
        self, *, mission_id: str, step_index: int, tool: str, action: str,
        args: dict[str, Any], idempotency_key: str, side_effecting: bool,
        started_at: str, count_attempt: bool = True,
        allow_readonly_replay: bool = False,
    ) -> bool:
        """Commit the write-ahead intent before any tool is invoked."""
        with self._connection() as db:
            db.execute(
                """INSERT INTO crash_steps(
                    mission_id, step_index, tool, action, args_json, idempotency_key,
                    side_effecting, status, started_at, attempt_count, runner_pid
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(mission_id, step_index) DO UPDATE SET
                    tool=excluded.tool, action=excluded.action, args_json=excluded.args_json,
                    idempotency_key=excluded.idempotency_key, side_effecting=excluded.side_effecting,
                    status='started', stdout='', stderr='', exit_code=NULL, normalized_code=NULL,
                    error='', paths_json='[]', result_json='null', verification_json='{}', started_at=excluded.started_at,
                    finished_at='', attempt_count=crash_steps.attempt_count+excluded.attempt_count,
                    runner_pid=excluded.runner_pid
                WHERE crash_steps.status='retry_authorized' OR (
                    ?=1 AND crash_steps.status='started' AND crash_steps.side_effecting=0
                    AND crash_steps.idempotency_key=excluded.idempotency_key
                )""",
                (mission_id, step_index, tool, action, json.dumps(args, ensure_ascii=False),
                 idempotency_key, int(side_effecting), "started", started_at, int(count_attempt),
                 os.getpid(), int(allow_readonly_replay)),
            )
            if db.execute("SELECT changes()").fetchone()[0] == 0:
                return False
            db.execute(
                "UPDATE crash_missions SET state='RUNNING', failure_reason='', updated_at=CURRENT_TIMESTAMP WHERE mission_id=?",
                (mission_id,),
            )
        return True

    def finish_step(self, mission_id: str, step_index: int, record: dict[str, Any]) -> None:
        """Atomically persist result evidence and terminal status after execution."""
        with self._connection() as db:
            db.execute(
                """UPDATE crash_steps SET status=?, stdout=?, stderr=?, exit_code=?, normalized_code=?,
                   error=?, paths_json=?, result_json=?, verification_json=?, finished_at=?, runner_pid=0
                   WHERE mission_id=? AND step_index=? AND status='started'""",
                (record["status"], record.get("stdout", ""), record.get("stderr", ""),
                 record.get("exit_code"), record.get("normalized_code"), record.get("error", ""),
                 json.dumps(record.get("paths", []), ensure_ascii=False),
                 json.dumps(record.get("result"), ensure_ascii=False, default=str),
                 json.dumps(record.get("verification", {}), ensure_ascii=False, default=str),
                 record.get("finished_at", ""), mission_id, step_index),
            )
            if db.total_changes == 0:
                raise RuntimeError(f"WAL step {mission_id}/{step_index} was not in started state")

    def mark_needs_review(self, mission_id: str, step_index: int, reason: str) -> None:
        with self._connection() as db:
            db.execute(
                "UPDATE crash_steps SET status='needs_review', error=?, stderr=?, finished_at=CURRENT_TIMESTAMP, runner_pid=0 "
                "WHERE mission_id=? AND step_index=? AND status='started'",
                (reason, reason, mission_id, step_index),
            )
            db.execute(
                "UPDATE crash_missions SET state='FAILED', failure_reason=?, updated_at=CURRENT_TIMESTAMP WHERE mission_id=?",
                (reason, mission_id),
            )


    def missions(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent mission summaries without exposing full step payloads."""
        bounded_limit = max(1, min(int(limit), 500))
        with self._connection() as db:
            rows = db.execute(
                "SELECT mission_id, objective, state, failure_reason, updated_at FROM crash_missions "
                "ORDER BY updated_at DESC, mission_id LIMIT ?",
                (bounded_limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def pending_approvals(self) -> list[dict[str, Any]]:
        """Return crash-safe steps awaiting explicit operator authorization."""
        with self._connection() as db:
            rows = db.execute(
                """SELECT m.mission_id, m.objective, m.state, m.failure_reason, m.updated_at,
                          s.step_index, s.tool, s.action, s.error AS approval_reason
                   FROM crash_missions m JOIN crash_steps s ON s.mission_id=m.mission_id
                   WHERE s.status='pending_approval' ORDER BY m.updated_at, m.mission_id, s.step_index"""
            ).fetchall()
            return [dict(row) for row in rows]

    def resolve_pending_approval(self, mission_id: str, step_index: int, approved: bool) -> dict[str, Any]:
        """Persist one explicit approval/denial decision atomically.

        Acquire the SQLite write reservation before reading the pending state. Without
        this, two concurrent operators/processes can both observe a pending step and
        race to overwrite each other's decision.
        """
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT steps_json FROM crash_missions WHERE mission_id=? AND state='WAITING_APPROVAL'",
                (mission_id,),
            ).fetchone()
            step = db.execute(
                "SELECT status FROM crash_steps WHERE mission_id=? AND step_index=?",
                (mission_id, step_index),
            ).fetchone()
            if row is None or step is None or step["status"] != "pending_approval":
                raise ValueError("The mission step is not awaiting approval.")
            if approved:
                saved_steps = _require_json_type(
                    _decode_json(row["steps_json"], "crash_missions.steps_json"),
                    list,
                    "crash_missions.steps_json",
                )
                if any(not isinstance(item, str) for item in saved_steps):
                    raise CrashSafeStoreCorruptionError(
                        "Stored crash-safe mission data is corrupt: crash_missions.steps_json must contain only strings."
                    )
                if not 0 <= step_index < len(saved_steps):
                    raise CrashSafeStoreCorruptionError(
                        "Stored crash-safe mission data is corrupt: approved step index is out of range."
                    )
                spec = _require_json_type(
                    _decode_json(saved_steps[step_index], "crash_missions.steps_json step"),
                    dict,
                    "crash_missions.steps_json step",
                )
                # Do not encode approval in the caller-controlled plan JSON. The
                # durable step status + exact audit marker below is the authorization source.
                saved_steps[step_index] = json.dumps(spec, ensure_ascii=False)
                db.execute("UPDATE crash_missions SET steps_json=?, state='RUNNING', failure_reason='', updated_at=CURRENT_TIMESTAMP WHERE mission_id=?",
                           (json.dumps(saved_steps, ensure_ascii=False), mission_id))
                db.execute("UPDATE crash_steps SET status='retry_authorized', error='', stderr='Operator explicitly approved this step.', finished_at='', runner_pid=0 WHERE mission_id=? AND step_index=?",
                           (mission_id, step_index))
            else:
                reason = "Denied by operator; action was not executed."
                db.execute("UPDATE crash_steps SET status='blocked', error=?, stderr=?, finished_at=CURRENT_TIMESTAMP, runner_pid=0 WHERE mission_id=? AND step_index=?",
                           (reason, reason, mission_id, step_index))
                db.execute("UPDATE crash_missions SET state='FAILED', failure_reason=?, updated_at=CURRENT_TIMESTAMP WHERE mission_id=?",
                           (reason, mission_id))
        return self.mission(mission_id) or {}

    def needs_review(self) -> list[dict[str, Any]]:
        with self._connection() as db:
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
        with self._connection() as db:
            # Serialize the read/decision/write sequence so concurrent retry and
            # abandon requests cannot both act on the same uncertain side effect.
            db.execute("BEGIN IMMEDIATE")
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
        with self._connection() as db:
            indices = [row[0] for row in db.execute(
                "SELECT step_index FROM crash_steps WHERE mission_id=? ORDER BY step_index", (mission_id,)
            )]
        return [record for index in indices if (record := self.step(mission_id, index)) is not None]
