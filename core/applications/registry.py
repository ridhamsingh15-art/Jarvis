"""
Application Registry.

Tracks installed applications, their versions, and current state.
"""
import logging
from typing import Optional
from .models import AppManifest, AppStatus, AppState

logger = logging.getLogger(__name__)

class AppRegistry:
    """In-memory registry of installed applications."""

    def __init__(self):
        self._manifests: dict[str, AppManifest] = {}
        self._statuses: dict[str, AppStatus] = {}

    def register(self, manifest: AppManifest) -> None:
        """Register a new application."""
        logger.info(f"Registering application: {manifest.id} v{manifest.version}")
        self._manifests[manifest.id] = manifest
        self._statuses[manifest.id] = AppStatus(
            app_id=manifest.id,
            state=AppState.INSTALLED,
            version=manifest.version
        )

    def unregister(self, app_id: str) -> None:
        """Remove an application from the registry."""
        if app_id in self._manifests:
            logger.info(f"Unregistering application: {app_id}")
            del self._manifests[app_id]
            del self._statuses[app_id]

    def update_state(self, app_id: str, new_state: AppState, error_message: Optional[str] = None) -> None:
        """Update the runtime state of an application."""
        if app_id not in self._statuses:
            raise KeyError(f"Application {app_id} not found in registry.")
            
        current = self._statuses[app_id]
        self._statuses[app_id] = AppStatus(
            app_id=app_id,
            state=new_state,
            version=current.version,
            uptime_seconds=current.uptime_seconds,
            error_message=error_message
        )
        logger.debug(f"App {app_id} transitioned to {new_state.value}")

    def get_manifest(self, app_id: str) -> Optional[AppManifest]:
        """Retrieve an application's manifest."""
        return self._manifests.get(app_id)

    def get_status(self, app_id: str) -> Optional[AppStatus]:
        """Retrieve an application's current runtime status."""
        return self._statuses.get(app_id)

    def list_installed(self) -> list[AppManifest]:
        """List all installed applications."""
        return list(self._manifests.values())
