"""
Permissions and Security Sandbox for AI Applications.
"""
import logging
from typing import Any

from core.models.primitives import Identifier

from .exceptions import AppPermissionError
from .models import AppManifest

logger = logging.getLogger(__name__)

class AppPermissionManager:
    """Enforces inherited plugin permission policies at the application level."""

    def __init__(self, core_permission_manager: Any):
        self._core = core_permission_manager

    def grant_permissions(self, manifest: AppManifest) -> None:
        """Request permission review and reject installation until grants exist.

        This method deliberately does not grant anything: only the explicit core
        permission manager's user-authorized ``grant`` operation can create a grant.
        """
        permissions = manifest.required_permissions
        logger.info("Checking permissions for %s", manifest.id)
        if not permissions:
            return

        request = getattr(self._core, "request_permissions", None)
        has_permission = getattr(self._core, "has_permission", None)
        if not callable(request) or not callable(has_permission):
            logger.warning("Permission backend is unavailable for application %s", manifest.id)
            raise AppPermissionError("Permission backend is unavailable; required permissions cannot be verified.")

        app_id = Identifier(manifest.id)
        try:
            request(app_id, permissions)
            missing = [permission for permission in permissions if not has_permission(app_id, permission)]
        except (TypeError, ValueError, AttributeError) as exc:
            logger.warning("Permission verification failed for %s (%s)", manifest.id, type(exc).__name__)
            raise AppPermissionError("Required permissions could not be verified.") from exc

        if missing:
            logger.warning("Application %s is missing %d required permission grant(s)", manifest.id, len(missing))
            raise AppPermissionError(
                f"Application '{manifest.id}' requires user-approved permissions before installation."
            )

    def check_permission(self, app_id: str, permission: str) -> bool:
        """Return true only when the core authority confirms an explicit grant."""
        has_permission = getattr(self._core, "has_permission", None)
        if not callable(has_permission):
            logger.warning("Permission backend is unavailable; denying %s.%s", app_id, permission)
            return False
        try:
            return bool(has_permission(Identifier(app_id), permission))
        except (TypeError, ValueError, AttributeError) as exc:
            logger.warning("Permission lookup failed for %s (%s)", app_id, type(exc).__name__)
            return False

    def assert_permission(self, app_id: str, permission: str) -> None:
        """Raise an error if the application lacks the required permission."""
        if not self.check_permission(app_id, permission):
            raise AppPermissionError(f"Application '{app_id}' lacks permission: {permission}")
