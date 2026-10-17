import threading

from core.models.primitives import Identifier

from .enums import CollaborationState
from .exceptions import CollaborationError
from .models import CollaborationSession


class CollaborationManager:
    """Thread-safe orchestrator for collaboration state transitions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, CollaborationSession] = {}

    def create_session(self, session_id: Identifier, participants: list[Identifier]) -> CollaborationSession:
        with self._lock:
            if session_id.value in self._sessions:
                raise CollaborationError(f"Session {session_id.value} already exists.")
                
            session = CollaborationSession(
                id=session_id,
                state=CollaborationState.INITIALIZED,
                participants=participants
            )
            self._sessions[session_id.value] = session
            return session

    def set_state(self, session_id: Identifier, state: CollaborationState) -> CollaborationSession:
        with self._lock:
            session = self._sessions.get(session_id.value)
            if not session:
                raise CollaborationError(f"Session {session_id.value} not found.")
                
            updated_session = CollaborationSession(
                id=session.id,
                state=state,
                participants=session.participants,
                timestamp=session.timestamp
            )
            self._sessions[session_id.value] = updated_session
            return updated_session

    def get_session(self, session_id: Identifier) -> CollaborationSession | None:
        with self._lock:
            return self._sessions.get(session_id.value)
