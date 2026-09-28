import builtins
import threading

from core.models.primitives import Identifier

from .enums import PluginCapability
from .interfaces import PluginRegistry
from .models import PluginDescriptor


class ThreadSafePluginRegistry(PluginRegistry):
    """Thread-safe, in-memory repository for plugins."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._plugins: dict[str, PluginDescriptor] = {}

    def register(self, descriptor: PluginDescriptor) -> None:
        with self._lock:
            self._plugins[descriptor.manifest.id.value] = descriptor

    def remove(self, plugin_id: Identifier) -> bool:
        with self._lock:
            if plugin_id.value in self._plugins:
                del self._plugins[plugin_id.value]
                return True
            return False

    def get(self, plugin_id: Identifier) -> PluginDescriptor | None:
        with self._lock:
            return self._plugins.get(plugin_id.value)

    def exists(self, plugin_id: Identifier) -> bool:
        with self._lock:
            return plugin_id.value in self._plugins

    def list(self) -> builtins.list[PluginDescriptor]:
        with self._lock:
            return builtins.list(self._plugins.values())

    def find_by_capability(self, capability: PluginCapability) -> builtins.list[PluginDescriptor]:
        with self._lock:
            return [
                p for p in self._plugins.values()
                if capability in p.manifest.capabilities
            ]
