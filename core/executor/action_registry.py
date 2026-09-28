import threading
from collections.abc import Callable

from .exceptions import ActionNotFoundError


class ActionRegistry:
    """Thread-safe registry mapping string identifiers to executable Callables."""
    
    def __init__(self):
        self._registry: dict[str, Callable] = {}
        self._lock = threading.Lock()
        
    def register(self, action_name: str, handler: Callable) -> None:
        """Registers a callable for a given action string."""
        with self._lock:
            self._registry[action_name] = handler
            
    def get(self, action_name: str) -> Callable:
        """Retrieves a handler. Raises ActionNotFoundError if missing."""
        with self._lock:
            handler = self._registry.get(action_name)
            if not handler:
                raise ActionNotFoundError(f"No execution handler registered for action: {action_name}")
            return handler
