import builtins

from core.models.primitives import Identifier

from .interfaces import PluginSandbox
from .models import PluginDescriptor


class PolicySandbox(PluginSandbox):
    """Enforces logical metadata-based constraints for plugins."""

    def __init__(self) -> None:
        self._permissions: dict[str, builtins.list[str]] = {}

    def track(self, descriptor: PluginDescriptor) -> None:
        plugin_id = descriptor.manifest.id.value
        self._permissions[plugin_id] = list(descriptor.manifest.permissions)

    def verify_permission(self, plugin_id: Identifier, permission: str) -> bool:
        if plugin_id.value not in self._permissions:
            return False
            
        # For this simple mock sandbox, if "*" is requested, it has all permissions
        # In a real scenario, this would be highly restricted or scoped.
        perms = self._permissions[plugin_id.value]
        if "*" in perms:
            return True
            
        return permission in perms
