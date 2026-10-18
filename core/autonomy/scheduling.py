"""Durable recurring-goal schedules with atomic claims and no catch-up bursts.

A schedule creates persisted goals. It never resumes a goal whose previous run was
interrupted; the goal manager's normal recovery path pauses that work for review.
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Schedule timestamps must be timezone-aware.")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Persisted schedule timestamp is missing timezone.")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class GoalSchedule:
    schedule_id: str
    description: str
    interval_seconds: int
    enabled: bool
    next_run_at: str
    created_at: str
    last_run_at: str | None = None
    last_status: str | None = None


@dataclass(frozen=True, slots=True)
class ScheduleRun:
    run_id: str
    schedule_id: str
    scheduled_for: str
    goal_id: str
    status: str
    error: str = ""


class SQLiteScheduleStore:
    """SQLite schedule definitions and a durable dispatch ledger."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _initialize(self) -> None:
        with self._lock, self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS autonomy_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    interval_seconds INTEGER NOT NULL CHECK(interval_seconds >= 60),
                    enabled INTEGER NOT NULL DEFAULT 1,
                    next_run_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_run_at TEXT,
                    last_status TEXT
                );
                CREATE TABLE IF NOT EXISTS autonomy_schedule_runs (
                    run_id TEXT PRIMARY KEY,
                    schedule_id TEXT NOT NULL,
                    scheduled_for TEXT NOT NULL,
                    goal_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(schedule_id, scheduled_for),
                    FOREIGN KEY(schedule_id) REFERENCES autonomy_schedules(schedule_id)
                );
                CREATE INDEX IF NOT EXISTS idx_autonomy_schedules_due
                    ON autonomy_schedules(enabled, next_run_at);
                CREATE INDEX IF NOT EXISTS idx_autonomy_runs_status
                    ON autonomy_schedule_runs(status, created_at);
            """)

    @staticmethod
    def _schedule(row: sqlite3.Row) -> GoalSchedule:
        return GoalSchedule(
            schedule_id=row["schedule_id"], description=row["description"],
            interval_seconds=int(row["interval_seconds"]), enabled=bool(row["enabled"]),
            next_run_at=row["next_run_at"], created_at=row["created_at"],
            last_run_at=row["last_run_at"], last_status=row["last_status"],
        )

    def create(self, description: str, interval_seconds: int, *, first_run_at: datetime | None = None) -> GoalSchedule:
        description = description.strip()
        if not description:
            raise ValueError("Scheduled goal description cannot be empty.")
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, int) or interval_seconds < 60:
            raise ValueError("Recurring interval must be an integer of at least 60 seconds.")
        now = _utcnow()
        first = first_run_at or (now + timedelta(seconds=interval_seconds))
        if first.tzinfo is None:
            raise ValueError("first_run_at must be timezone-aware.")
        schedule_id = "schedule_" + uuid.uuid4().hex
        with self._lock, self._connect() as db:
            db.execute(
                """INSERT INTO autonomy_schedules
                   (schedule_id, description, interval_seconds, enabled, next_run_at, created_at)
                   VALUES(?,?,?,1,?,?)""",
                (schedule_id, description, interval_seconds, _iso(first), _iso(now)),
            )
            row = db.execute("SELECT * FROM autonomy_schedules WHERE schedule_id=?", (schedule_id,)).fetchone()
        return self._schedule(row)

    def list(self) -> list[GoalSchedule]:
        with self._lock, self._connect() as db:
            rows = db.execute("SELECT * FROM autonomy_schedules ORDER BY created_at, schedule_id").fetchall()
        return [self._schedule(row) for row in rows]

    def get(self, schedule_id: str) -> GoalSchedule | None:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM autonomy_schedules WHERE schedule_id=?", (schedule_id,)).fetchone()
        return self._schedule(row) if row else None

    def set_enabled(self, schedule_id: str, enabled: bool) -> GoalSchedule:
        with self._lock, self._connect() as db:
            changed = db.execute(
                "UPDATE autonomy_schedules SET enabled=? WHERE schedule_id=?",
                (int(bool(enabled)), schedule_id),
            ).rowcount
            if not changed:
                raise ValueError(f"Unknown schedule {schedule_id}.")
            row = db.execute("SELECT * FROM autonomy_schedules WHERE schedule_id=?", (schedule_id,)).fetchone()
        return self._schedule(row)

    def delete(self, schedule_id: str) -> None:
        with self._lock, self._connect() as db:
            if db.execute("SELECT 1 FROM autonomy_schedules WHERE schedule_id=?", (schedule_id,)).fetchone() is None:
                raise ValueError(f"Unknown schedule {schedule_id}.")
            db.execute("DELETE FROM autonomy_schedule_runs WHERE schedule_id=?", (schedule_id,))
            db.execute("DELETE FROM autonomy_schedules WHERE schedule_id=?", (schedule_id,))

    def claim_due(self, now: datetime | None = None) -> list[ScheduleRun]:
        """Atomically create run ledger entries; overdue intervals never burst-replay."""
        instant = now or _utcnow()
        if instant.tzinfo is None:
            raise ValueError("now must be timezone-aware.")
        now_text = _iso(instant)
        claimed: list[ScheduleRun] = []
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            due = db.execute(
                "SELECT * FROM autonomy_schedules WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at",
                (now_text,),
            ).fetchall()
            for row in due:
                scheduled_for = row["next_run_at"]
                schedule_id = row["schedule_id"]
                run_id = f"{schedule_id}:{scheduled_for}"
                goal_id = "scheduled_" + uuid.uuid5(uuid.NAMESPACE_URL, run_id).hex
                db.execute(
                    """INSERT OR IGNORE INTO autonomy_schedule_runs
                       (run_id, schedule_id, scheduled_for, goal_id, status, created_at, updated_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (run_id, schedule_id, scheduled_for, goal_id, "PENDING", now_text, now_text),
                )
                # Advance from now rather than the old due time: a missed interval
                # creates at most one run and cannot produce a catch-up storm.
                next_run = _iso(instant + timedelta(seconds=int(row["interval_seconds"])))
                db.execute(
                    "UPDATE autonomy_schedules SET next_run_at=? WHERE schedule_id=?",
                    (next_run, schedule_id),
                )
                run = db.execute("SELECT * FROM autonomy_schedule_runs WHERE run_id=?", (run_id,)).fetchone()
                if run and run["status"] == "PENDING":
                    claimed.append(ScheduleRun(run["run_id"], schedule_id, scheduled_for, goal_id, run["status"], run["error"]))
            db.commit()
        return claimed

    def pending_runs(self, limit: int = 1000) -> list[ScheduleRun]:
        """List durable undispatched run records for crash-safe dispatch retries."""
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT * FROM autonomy_schedule_runs WHERE status='PENDING' ORDER BY created_at LIMIT ?",
                (max(1, min(limit, 5000)),),
            ).fetchall()
        return [
            ScheduleRun(row["run_id"], row["schedule_id"], row["scheduled_for"],
                        row["goal_id"], row["status"], row["error"])
            for row in rows
        ]

    def claim_pending_runs(self, limit: int = 1000) -> list[ScheduleRun]:
        """Atomically lease pending dispatches so two JARVIS processes cannot start the same run."""
        now_text = _iso(_utcnow())
        claimed: list[ScheduleRun] = []
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT * FROM autonomy_schedule_runs WHERE status='PENDING' ORDER BY created_at LIMIT ?",
                (max(1, min(limit, 5000)),),
            ).fetchall()
            for row in rows:
                updated = db.execute(
                    "UPDATE autonomy_schedule_runs SET status='RUNNING', error='', updated_at=? "
                    "WHERE run_id=? AND status='PENDING'",
                    (now_text, row["run_id"]),
                ).rowcount
                if updated:
                    claimed.append(ScheduleRun(
                        row["run_id"], row["schedule_id"], row["scheduled_for"],
                        row["goal_id"], "RUNNING", "",
                    ))
            db.commit()
        return claimed

    def run_for_goal(self, goal_id: str) -> ScheduleRun | None:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT * FROM autonomy_schedule_runs WHERE goal_id=?",
                (goal_id,),
            ).fetchone()
        if row is None:
            return None
        return ScheduleRun(
            row["run_id"], row["schedule_id"], row["scheduled_for"],
            row["goal_id"], row["status"], row["error"],
        )

    def update_run(self, run_id: str, status: str, error: str = "") -> None:
        allowed = {"PENDING", "RUNNING", "COMPLETED", "FAILED", "PAUSED", "CANCELLED"}
        if status not in allowed:
            raise ValueError(f"Unsupported schedule run state {status!r}.")
        now = _iso(_utcnow())
        with self._lock, self._connect() as db:
            row = db.execute("SELECT schedule_id FROM autonomy_schedule_runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown schedule run {run_id}.")
            db.execute(
                "UPDATE autonomy_schedule_runs SET status=?, error=?, updated_at=? WHERE run_id=?",
                (status, error[:1000], now, run_id),
            )
            db.execute(
                "UPDATE autonomy_schedules SET last_run_at=?, last_status=? WHERE schedule_id=?",
                (now, status, row["schedule_id"]),
            )

    def runs(self, schedule_id: str | None = None, limit: int = 100) -> list[ScheduleRun]:
        with self._lock, self._connect() as db:
            if schedule_id:
                rows = db.execute(
                    "SELECT * FROM autonomy_schedule_runs WHERE schedule_id=? ORDER BY created_at DESC LIMIT ?",
                    (schedule_id, max(1, min(limit, 1000))),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM autonomy_schedule_runs ORDER BY created_at DESC LIMIT ?",
                    (max(1, min(limit, 1000)),),
                ).fetchall()
        return [ScheduleRun(row["run_id"], row["schedule_id"], row["scheduled_for"], row["goal_id"], row["status"], row["error"]) for row in rows]
