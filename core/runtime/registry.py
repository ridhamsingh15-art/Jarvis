"""
Component registry for JARVIS AIOS.
"""
import threading

from .exceptions import ComponentNotFoundError, ComponentRegistrationError
from .interfaces import RuntimeComponent


class ComponentRegistry:
    """Thread-safe storage for active runtime components."""

    def __init__(self) -> None:
        self._components: dict[str, RuntimeComponent] = {}
        self._lock = threading.RLock()

    def register(self, component: RuntimeComponent) -> None:
        with self._lock:
            cid = component.metadata.id
            if cid in self._components:
                raise ComponentRegistrationError(
                    f"Component with ID '{cid}' is already registered."
                )
            self._components[cid] = component

    def unregister(self, component_id: str) -> None:
        with self._lock:
            if component_id not in self._components:
                raise ComponentNotFoundError(f"Component '{component_id}' not found.")
            del self._components[component_id]

    def get(self, component_id: str) -> RuntimeComponent:
        with self._lock:
            comp = self._components.get(component_id)
            if not comp:
                raise ComponentNotFoundError(f"Component '{component_id}' not found.")
            return comp

    def get_all(self) -> list[RuntimeComponent]:
        with self._lock:
            return list(self._components.values())
