import threading
from typing import Dict, List, Optional
from .interfaces import RuntimeComponent
from .exceptions import ComponentRegistrationError, ComponentResolutionError

class RuntimeRegistry:
    """Thread-safe O(1) registry for Runtime components."""
    
    def __init__(self):
        self._components: Dict[str, RuntimeComponent] = {}
        self._lock = threading.Lock()

    def register(self, component: RuntimeComponent) -> None:
        name = component.metadata().name
        with self._lock:
            if name in self._components:
                raise ComponentRegistrationError(f"Component '{name}' is already registered.")
            self._components[name] = component

    def unregister(self, name: str) -> bool:
        with self._lock:
            if name in self._components:
                del self._components[name]
                return True
        return False

    def resolve(self, name: str) -> RuntimeComponent:
        with self._lock:
            if name not in self._components:
                raise ComponentResolutionError(f"Component '{name}' not found.")
            return self._components[name]

    def list_components(self) -> List[RuntimeComponent]:
        with self._lock:
            return list(self._components.values())
