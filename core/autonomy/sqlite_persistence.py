"""SQLite-backed persistence for long-running autonomous goals and plans.

Interrupted RUNNING/PLANNING goals are recovered as PAUSED, never replayed
silently. Their last side effect may have succeeded before a crash.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from core.models.primitives import Identifier, Timestamp

from .enums import GoalPriority, GoalState, RetryStrategy, StepState
from .exceptions import PersistenceError
from .interfaces import IGoalPersistence
from .models import Goal, GoalPlan, GoalStep


class SQLiteGoalPersistence(IGoalPersistence):
    """Thread-safe, durable implementation of ``IGoalPersistence``."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    def _initialize(self) -> None:
        try:
            with self._connect() as db:
                db.execute("PRAGMA journal_mode = WAL")
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS autonomy_metadata (
                        key TEXT PRIMARY KEY, value TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS autonomy_goals (
                        id TEXT PRIMARY KEY, state TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS autonomy_plans (
                        goal_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(goal_id) REFERENCES autonomy_goals(id) ON DELETE CASCADE
                    );
                """)
                row = db.execute("SELECT value FROM autonomy_metadata WHERE key='schema_version'").fetchone()
                if row is None:
                    db.execute("INSERT INTO autonomy_metadata(key, value) VALUES('schema_version', ?)", (str(self.SCHEMA_VERSION),))
                elif int(row["value"]) != self.SCHEMA_VERSION:
                    raise PersistenceError(f"Unsupported autonomy database schema {row['value']}; expected {self.SCHEMA_VERSION}.")
        except sqlite3.Error as exc:
            raise PersistenceError(f"Could not initialize autonomy database: {exc}") from exc

    @staticmethod
    def _decode_goal(raw: dict[str, Any]) -> Goal:
        return Goal(
            id=Identifier.from_dict(raw["id"]),
            description=raw["description"],
            state=GoalState(raw.get("state", GoalState.CREATED.value)),
            priority=GoalPriority(raw.get("priority", GoalPriority.NORMAL.value)),
            metadata=raw.get("metadata") or {},
            timestamp=Timestamp.from_dict(raw["timestamp"]) if isinstance(raw.get("timestamp"), dict) else Timestamp(),
        )

    @staticmethod
    def _decode_plan(raw: dict[str, Any]) -> GoalPlan:
        steps = []
        for item in raw.get("steps", []):
            steps.append(GoalStep(
                id=Identifier.from_dict(item["id"]),
                description=item["description"],
                state=StepState(item.get("state", StepState.PENDING.value)),
                dependencies=[Identifier.from_dict(dep) if isinstance(dep, dict) else Identifier(str(dep)) for dep in item.get("dependencies", [])],
                context=item.get("context") or {},
                retry_strategy=RetryStrategy(item.get("retry_strategy", RetryStrategy.LINEAR.value)),
                max_retries=int(item.get("max_retries", 3)),
                retry_count=int(item.get("retry_count", 0)),
            ))
        return GoalPlan(goal_id=Identifier.from_dict(raw["goal_id"]), steps=steps)

    def save_goal(self, goal: Goal) -> None:
        if not isinstance(goal, Goal):
            raise PersistenceError("save_goal expects a Goal instance.")
        payload = json.dumps(goal.to_dict(), ensure_ascii=False, sort_keys=True)
        with self._lock:
            try:
                with self._connect() as db:
                    db.execute("""INSERT INTO autonomy_goals(id, state, payload_json, updated_at)
                        VALUES(?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(id) DO UPDATE SET
                        state=excluded.state, payload_json=excluded.payload_json,
                        updated_at=CURRENT_TIMESTAMP""", (goal.id.value, goal.state.value, payload))
            except sqlite3.Error as exc:
                raise PersistenceError(f"Could not save goal {goal.id.value}: {exc}") from exc

    def get_goal(self, goal_id: Identifier) -> Goal | None:
        if not isinstance(goal_id, Identifier):
            raise PersistenceError("get_goal expects an Identifier.")
        with self._lock:
            try:
                with self._connect() as db:
                    row = db.execute("SELECT payload_json FROM autonomy_goals WHERE id=?", (goal_id.value,)).fetchone()
            except sqlite3.Error as exc:
                raise PersistenceError(f"Could not load goal {goal_id.value}: {exc}") from exc
        if row is None:
            return None
        try:
            return self._decode_goal(json.loads(row["payload_json"]))
        except (ValueError, TypeError, KeyError) as exc:
            raise PersistenceError(f"Stored goal {goal_id.value} is invalid: {exc}") from exc

    def save_plan(self, plan: GoalPlan) -> None:
        if not isinstance(plan, GoalPlan):
            raise PersistenceError("save_plan expects a GoalPlan instance.")
        payload = json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True)
        with self._lock:
            try:
                with self._connect() as db:
                    if db.execute("SELECT 1 FROM autonomy_goals WHERE id=?", (plan.goal_id.value,)).fetchone() is None:
                        raise PersistenceError(f"Cannot save a plan for unknown goal {plan.goal_id.value}.")
                    db.execute("""INSERT INTO autonomy_plans(goal_id, payload_json, updated_at)
                        VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(goal_id) DO UPDATE SET
                        payload_json=excluded.payload_json, updated_at=CURRENT_TIMESTAMP""", (plan.goal_id.value, payload))
            except sqlite3.Error as exc:
                raise PersistenceError(f"Could not save plan for {plan.goal_id.value}: {exc}") from exc

    def get_plan(self, goal_id: Identifier) -> GoalPlan | None:
        if not isinstance(goal_id, Identifier):
            raise PersistenceError("get_plan expects an Identifier.")
        with self._lock:
            try:
                with self._connect() as db:
                    row = db.execute("SELECT payload_json FROM autonomy_plans WHERE goal_id=?", (goal_id.value,)).fetchone()
            except sqlite3.Error as exc:
                raise PersistenceError(f"Could not load plan for {goal_id.value}: {exc}") from exc
        if row is None:
            return None
        try:
            return self._decode_plan(json.loads(row["payload_json"]))
        except (ValueError, TypeError, KeyError) as exc:
            raise PersistenceError(f"Stored plan for {goal_id.value} is invalid: {exc}") from exc

    def list_goals(self) -> list[Goal]:
        with self._lock:
            try:
                with self._connect() as db:
                    rows = db.execute("SELECT payload_json FROM autonomy_goals ORDER BY updated_at, id").fetchall()
            except sqlite3.Error as exc:
                raise PersistenceError(f"Could not list goals: {exc}") from exc
        try:
            return [self._decode_goal(json.loads(row["payload_json"])) for row in rows]
        except (ValueError, TypeError, KeyError) as exc:
            raise PersistenceError(f"Stored goal collection contains invalid data: {exc}") from exc

    def recover_interrupted_goals(self) -> list[Goal]:
        """Persist interrupted work as PAUSED for explicit, safe resumption."""
        recovered: list[Goal] = []
        for goal in self.list_goals():
            if goal.state in (GoalState.RUNNING, GoalState.PLANNING):
                paused = goal.copy(state=GoalState.PAUSED)
                self.save_goal(paused)
                recovered.append(paused)
        return recovered
