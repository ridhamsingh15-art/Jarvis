"""
Experience Repository.

Thread-safe in-memory store for ExperienceRecords and Lessons, with an optional
SQLite persistence backend for durability across restarts.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from .exceptions import DuplicateExperienceError
from .models import ExperienceRecord, Lesson

logger = logging.getLogger(__name__)


class InMemoryExperienceRepository:
    """
    Fast, thread-safe in-memory store.
    Suitable for tests and short-lived sessions.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, ExperienceRecord] = {}
        self._lessons: dict[str, Lesson] = {}

    # ------------------------------------------------------------------
    # ExperienceRecords
    # ------------------------------------------------------------------

    def save_record(self, record: ExperienceRecord) -> None:
        with self._lock:
            if record.id in self._records:
                raise DuplicateExperienceError(f"Experience {record.id} already stored.")
            self._records[record.id] = record

    def get_record(self, record_id: str) -> Optional[ExperienceRecord]:
        with self._lock:
            return self._records.get(record_id)

    def list_records(self) -> list[ExperienceRecord]:
        with self._lock:
            return list(self._records.values())

    def find_records_by_topic(self, topic: str) -> list[ExperienceRecord]:
        topic_lower = topic.lower()
        with self._lock:
            return [r for r in self._records.values() if topic_lower in r.topic.lower()]

    def find_records_by_mission(self, mission_id: str) -> list[ExperienceRecord]:
        with self._lock:
            return [r for r in self._records.values() if r.mission_id == mission_id]

    # ------------------------------------------------------------------
    # Lessons
    # ------------------------------------------------------------------

    def save_lesson(self, lesson: Lesson) -> None:
        with self._lock:
            self._lessons[lesson.id] = lesson

    def get_lesson(self, lesson_id: str) -> Optional[Lesson]:
        with self._lock:
            return self._lessons.get(lesson_id)

    def list_lessons(self) -> list[Lesson]:
        with self._lock:
            return list(self._lessons.values())

    def find_lessons_by_topic(self, topic: str) -> list[Lesson]:
        topic_lower = topic.lower()
        with self._lock:
            return [l for l in self._lessons.values() if topic_lower in l.topic.lower()]


class SqliteExperienceRepository(InMemoryExperienceRepository):
    """
    Durable SQLite-backed experience store.
    Falls back to in-memory if the database cannot be opened.
    Records are serialised as JSON blobs for simplicity.
    """

    _CREATE_RECORDS_DDL = """
        CREATE TABLE IF NOT EXISTS experience_records (
            id TEXT PRIMARY KEY,
            mission_id TEXT,
            topic TEXT,
            data TEXT NOT NULL
        )
    """
    _CREATE_LESSONS_DDL = """
        CREATE TABLE IF NOT EXISTS experience_lessons (
            id TEXT PRIMARY KEY,
            topic TEXT,
            data TEXT NOT NULL
        )
    """

    def __init__(self, db_path: str) -> None:
        super().__init__()
        self._db_path = db_path
        try:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.execute(self._CREATE_RECORDS_DDL)
            self._conn.execute(self._CREATE_LESSONS_DDL)
            self._conn.commit()
            self._load_from_db()
            logger.info(f"Experience DB ready: {db_path}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Could not open experience DB: {e}. Using in-memory only.")
            self._conn = None  # type: ignore[assignment]

    def _load_from_db(self) -> None:
        """Populate the in-memory cache from SQLite on startup."""
        import dataclasses
        cur = self._conn.execute("SELECT data FROM experience_records")
        for (blob,) in cur.fetchall():
            try:
                data = json.loads(blob)
                # Reconstruct ExperienceRecord from dict (shallow)
                record = ExperienceRecord(**{
                    k: v for k, v in data.items()
                    if k in {f.name for f in dataclasses.fields(ExperienceRecord)}
                })
                self._records[record.id] = record
            except Exception:  # noqa: BLE001
                pass

    def save_record(self, record: ExperienceRecord) -> None:
        super().save_record(record)
        if self._conn:
            import dataclasses
            blob = json.dumps(dataclasses.asdict(record), default=str)
            self._conn.execute(
                "INSERT OR REPLACE INTO experience_records (id, mission_id, topic, data) VALUES (?, ?, ?, ?)",
                (record.id, record.mission_id, record.topic, blob)
            )
            self._conn.commit()

    def save_lesson(self, lesson: Lesson) -> None:
        super().save_lesson(lesson)
        if self._conn:
            import dataclasses
            blob = json.dumps(dataclasses.asdict(lesson), default=str)
            self._conn.execute(
                "INSERT OR REPLACE INTO experience_lessons (id, topic, data) VALUES (?, ?, ?)",
                (lesson.id, lesson.topic, blob)
            )
            self._conn.commit()
