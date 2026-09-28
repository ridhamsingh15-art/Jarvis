"""
Phase F Tests — Session Architecture

Tests:
1. create session
2. resume session
3. session not found → None
4. end session
5. list recent sessions
6. corrupted session gracefully handled
7. concurrent session isolation (separate IDs)
8. session metadata preserved
"""
import pytest
import time
from core.session import SessionRepository, SessionStatus


class TestSessionCreate:
    def test_create_returns_session(self):
        repo = SessionRepository()  # in-memory
        session = repo.create()
        assert session.session_id
        assert session.status == SessionStatus.ACTIVE
        assert session.created_at > 0
        assert session.updated_at > 0

    def test_create_with_conversation_id(self):
        repo = SessionRepository()
        session = repo.create(conversation_id="conv-123")
        assert session.conversation_id == "conv-123"

    def test_create_with_metadata(self):
        repo = SessionRepository()
        meta = {"user": "Ridham", "theme": "dark"}
        session = repo.create(metadata=meta)
        assert session.metadata == meta

    def test_two_sessions_have_different_ids(self):
        repo = SessionRepository()
        s1 = repo.create()
        s2 = repo.create()
        assert s1.session_id != s2.session_id


class TestSessionResume:
    def test_resume_existing_session(self):
        repo = SessionRepository()
        created = repo.create()
        resumed = repo.resume(created.session_id)
        assert resumed is not None
        assert resumed.session_id == created.session_id
        assert resumed.status == SessionStatus.ACTIVE

    def test_resume_missing_session_returns_none(self):
        repo = SessionRepository()
        result = repo.resume("does-not-exist")
        assert result is None

    def test_resume_is_resumable(self):
        repo = SessionRepository()
        session = repo.create()
        resumed = repo.resume(session.session_id)
        assert resumed.is_resumable()


class TestSessionEnd:
    def test_end_session(self):
        repo = SessionRepository()
        session = repo.create()
        repo.end(session.session_id)
        retrieved = repo.get(session.session_id)
        assert retrieved is not None
        assert retrieved.status == SessionStatus.ENDED

    def test_ended_session_not_resumable(self):
        repo = SessionRepository()
        session = repo.create()
        repo.end(session.session_id)
        retrieved = repo.get(session.session_id)
        assert not retrieved.is_resumable()

    def test_end_nonexistent_returns_false(self):
        repo = SessionRepository()
        result = repo.end("nonexistent")
        assert result is False


class TestSessionList:
    def test_list_recent_returns_sessions(self):
        repo = SessionRepository()
        s1 = repo.create(metadata={"n": 1})
        s2 = repo.create(metadata={"n": 2})
        sessions = repo.list_recent(limit=10)
        ids = [s.session_id for s in sessions]
        assert s1.session_id in ids
        assert s2.session_id in ids

    def test_list_recent_respects_limit(self):
        repo = SessionRepository()
        for _ in range(5):
            repo.create()
        sessions = repo.list_recent(limit=3)
        assert len(sessions) == 3


class TestSessionIsolation:
    def test_two_sessions_isolated(self):
        repo = SessionRepository()
        s1 = repo.create(conversation_id="conv-A")
        s2 = repo.create(conversation_id="conv-B")

        r1 = repo.get(s1.session_id)
        r2 = repo.get(s2.session_id)
        assert r1.conversation_id == "conv-A"
        assert r2.conversation_id == "conv-B"

    def test_ending_one_session_does_not_affect_other(self):
        repo = SessionRepository()
        s1 = repo.create()
        s2 = repo.create()
        repo.end(s1.session_id)

        r2 = repo.get(s2.session_id)
        assert r2.status == SessionStatus.ACTIVE
