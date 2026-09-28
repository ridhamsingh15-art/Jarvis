import threading
from typing import Any

from core.cognition.enums import IntentType


class ShortTermContext:
    """Thread-safe short-term conversation context."""

    def __init__(self, max_history: int = 10):
        self._lock = threading.RLock()
        self._max_history = max_history
        self._intents: list[IntentType] = []
        self._actions: list[str] = []
        self._messages: list[dict[str, str]] = []
        self._pending_slots: dict[str, str] = {}
        self._system_notes: list[str] = []

    def add_intent(self, intent: IntentType) -> None:
        with self._lock:
            self._intents.append(intent)
            if len(self._intents) > self._max_history:
                self._intents.pop(0)

    def add_action(self, action: str) -> None:
        with self._lock:
            self._actions.append(action)
            if len(self._actions) > self._max_history:
                self._actions.pop(0)

    def add_message(self, role: str, content: str) -> None:
        with self._lock:
            self._messages.append({"role": role, "content": content})
            if len(self._messages) > self._max_history:
                self._messages.pop(0)

    def set_pending_slot(self, name: str, prompt: str) -> None:
        """Record a conversational value the assistant is waiting to receive."""
        with self._lock:
            self._pending_slots[name] = prompt

    def get_pending_slot(self, name: str) -> str | None:
        """Return the prompt for an unresolved conversational value."""
        with self._lock:
            return self._pending_slots.get(name)

    def clear_pending_slot(self, name: str) -> None:
        """Mark a pending conversational value as resolved."""
        with self._lock:
            self._pending_slots.pop(name, None)

    def get_context_summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "recent_intents": list(self._intents),
                "recent_actions": list(self._actions),
                "messages": list(self._messages),
                "pending_slots": dict(self._pending_slots),
                "system_notes": list(self._system_notes),
            }

    def inject_system_note(self, note: str) -> None:
        """Inject a system-level note (e.g., prior experience) into the context."""
        with self._lock:
            if not hasattr(self, "_system_notes"):
                self._system_notes: list[str] = []
            self._system_notes.append(note)

    def get_system_notes(self) -> list[str]:
        with self._lock:
            return list(getattr(self, "_system_notes", []))
