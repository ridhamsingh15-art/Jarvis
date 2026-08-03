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

    def get_context_summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "recent_intents": list(self._intents),
                "recent_actions": list(self._actions),
                "messages": list(self._messages)
            }
