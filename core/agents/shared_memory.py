import copy
import threading
from typing import Any

from core.models.primitives import Identifier

from .interfaces import ISharedMemory
from .models import SharedContext


class ThreadSafeSharedMemory(ISharedMemory):
    """KV Store isolated by thread-safe locks for cross-agent synchronization."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._store: dict[str, Any] = {}

    def write(self, key: str, value: Any) -> None:
        with self._lock:
            # Deep copy to ensure mutation doesn't break boundaries
            self._store[key] = copy.deepcopy(value)

    def read(self, key: str) -> Any | None:
        with self._lock:
            val = self._store.get(key)
            if val is not None:
                return copy.deepcopy(val)
            return None

    def snapshot(self, session_id: Identifier) -> SharedContext:
        with self._lock:
            return SharedContext(
                session_id=session_id,
                read_only_data=copy.deepcopy(self._store)
            )
