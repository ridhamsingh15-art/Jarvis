import threading
from typing import Any


class InternetCache:
    """Wraps an RLock around deep-copied dictionaries mapping URL strings."""
    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._lock = threading.RLock()
        
    def get(self, url: str) -> Any | None:
        with self._lock:
            return self._cache.get(url)
            
    def set(self, url: str, data: Any) -> None:
        with self._lock:
            self._cache[url] = data
