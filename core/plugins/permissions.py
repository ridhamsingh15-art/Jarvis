"""
Plugin Permissions System.

Manages user-granted permissions for plugins. Plugins must explicitly request
permissions in their manifest; users must explicitly grant them before the
sandbox allows access.
"""
import builtins
import logging
from enum import StrEnum
from dataclasses import dataclass, field

from core.models.primitives import Identifier, Timestamp

from .exceptions import PluginSecurityError

logger = logging.getLogger(__name__)


class PermissionType(StrEnum):
    FILESYSTEM  = "filesystem"
    NETWORK     = "network"
    CLIPBOARD   = "clipboard"
    MICROPHONE  = "microphone"
    CAMERA      = "camera"
    AUTOMATION  = "automation"
    DESKTOP     = "desktop_control"


PERMISSION_DESCRIPTIONS: dict[str, str] = {
    PermissionType.FILESYSTEM:  "Read/write files on the local filesystem.",
    PermissionType.NETWORK:     "Make outbound network requests.",
    PermissionType.CLIPBOARD:   "Read from and write to the system clipboard.",
    PermissionType.MICROPHONE:  "Access the microphone for audio capture.",
    PermissionType.CAMERA:      "Access the camera for video capture.",
    PermissionType.AUTOMATION:  "Automate OS-level actions (keyboard, mouse).",
    PermissionType.DESKTOP:     "Control the desktop and application windows.",
}


@dataclass
class PermissionGrant:
    """Records a user's explicit permission grant for a plugin."""
    plugin_id: str
    permission: str
    granted_at: Timestamp = field(default_factory=Timestamp)
    granted_by: str = "user"


class PermissionManager:
    """
    Central authority for plugin permission grants.
    Plugins may only access system resources if the user has explicitly granted
    the corresponding permission.
    """

    def __init__(self) -> None:
        # { plugin_id -> set of granted permissions }
        self._grants: dict[str, builtins.set[str]] = {}

    # ------------------------------------------------------------------
    # User-facing permission management
    # ------------------------------------------------------------------

    def request_permissions(self, plugin_id: Identifier, permissions: builtins.list[str]) -> dict[str, str]:
        """
        Returns a human-readable summary of permissions a plugin is requesting,
        so the UI can present them to the user for confirmation.
        """
        return {
            p: PERMISSION_DESCRIPTIONS.get(p, f"Unknown permission: {p}")
            for p in permissions
        }

    def grant(self, plugin_id: Identifier, permission: str) -> PermissionGrant:
        """Explicitly grant a permission to a plugin."""
        pid = plugin_id.value
        if pid not in self._grants:
            self._grants[pid] = set()
        self._grants[pid].add(permission)
        grant = PermissionGrant(plugin_id=pid, permission=permission)
        logger.info(f"Permission granted: plugin={pid}, permission={permission}")
        return grant

    def revoke(self, plugin_id: Identifier, permission: str) -> None:
        """Revoke a previously granted permission."""
        pid = plugin_id.value
        if pid in self._grants:
            self._grants[pid].discard(permission)
        logger.info(f"Permission revoked: plugin={pid}, permission={permission}")

    def revoke_all(self, plugin_id: Identifier) -> None:
        """Revoke all permissions for a plugin (e.g., on uninstall)."""
        self._grants.pop(plugin_id.value, None)

    def has_permission(self, plugin_id: Identifier, permission: str) -> bool:
        """Check whether a plugin currently holds a specific permission."""
        return permission in self._grants.get(plugin_id.value, set())

    def assert_permission(self, plugin_id: Identifier, permission: str) -> None:
        """Raise PluginSecurityError if the plugin does not hold the permission."""
        if not self.has_permission(plugin_id, permission):
            raise PluginSecurityError(
                f"Plugin '{plugin_id.value}' does not have permission '{permission}'. "
                f"User must grant it explicitly."
            )

    def list_grants(self, plugin_id: Identifier) -> builtins.list[str]:
        """List all permissions currently granted to a plugin."""
        return sorted(self._grants.get(plugin_id.value, set()))
