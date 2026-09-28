"""
Application Updater.

Handles versioning, migrations, and compatibility checks.
"""
import logging
from typing import Any
from .models import InstallResult
from .manifest import ManifestParser
from .registry import AppRegistry
from .dependency_manager import AppDependencyManager
from .permissions import AppPermissionManager
from .exceptions import AppUpdateError, DependencyResolutionError, InvalidManifestError

logger = logging.getLogger(__name__)

class AppUpdater:
    """Updates AI applications within the runtime."""

    def __init__(
        self,
        registry: AppRegistry,
        dependency_manager: AppDependencyManager,
        permission_manager: AppPermissionManager
    ):
        self._registry = registry
        self._dependency_manager = dependency_manager
        self._permission_manager = permission_manager
        self._manifest_parser = ManifestParser()

    def update(self, app_id: str, raw_manifest_data: dict[str, Any]) -> InstallResult:
        """
        Attempt to update an application. Rollback on failure.
        """
        logger.info(f"Attempting to update application {app_id}...")
        
        # 1. Capture current state for rollback
        current_manifest = self._registry.get_manifest(app_id)
        if not current_manifest:
            return InstallResult(
                success=False,
                errors=[f"Application {app_id} is not installed; cannot update."]
            )
            
        try:
            # 2. Parse new manifest
            new_manifest = self._manifest_parser.parse(raw_manifest_data)
            if new_manifest.id != app_id:
                raise AppUpdateError("New manifest ID does not match current app ID.")
                
            # 3. Resolve dependencies
            resolved = self._dependency_manager.resolve_dependencies(new_manifest)
            
            # 4. Update permissions
            self._permission_manager.grant_permissions(new_manifest)
            
            # 5. Apply update to registry
            self._registry.unregister(app_id)
            self._registry.register(new_manifest)
            
            logger.info(f"Successfully updated {app_id} from {current_manifest.version} to {new_manifest.version}")
            return InstallResult(
                success=True,
                app_id=app_id,
                version=new_manifest.version,
                resolved_dependencies=resolved
            )
            
        except (InvalidManifestError, DependencyResolutionError, AppUpdateError) as e:
            logger.error(f"Update failed: {e}. Rolling back...")
            self._rollback(app_id, current_manifest)
            return InstallResult(
                success=False,
                errors=[str(e)]
            )
        except Exception as e:
            logger.error(f"Unexpected error during update: {e}. Rolling back...")
            self._rollback(app_id, current_manifest)
            return InstallResult(
                success=False,
                errors=[f"Unexpected error: {str(e)}"]
            )

    def _rollback(self, app_id: str, manifest: Any) -> None:
        """Rollback the application registry state to the previous manifest."""
        logger.info(f"Rolling back {app_id} to v{manifest.version}")
        self._registry.unregister(app_id)
        self._registry.register(manifest)
