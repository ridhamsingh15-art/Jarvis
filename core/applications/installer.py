"""
Application Installer.

Handles installing new applications, parsing their manifest, and resolving dependencies.
"""
import logging
from typing import Any
from .models import InstallResult
from .manifest import ManifestParser
from .registry import AppRegistry
from .dependency_manager import AppDependencyManager
from .permissions import AppPermissionManager
from .exceptions import AppInstallError, DependencyResolutionError, InvalidManifestError

logger = logging.getLogger(__name__)

class AppInstaller:
    """Installs AI applications into the runtime."""

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

    def install(self, raw_manifest_data: dict[str, Any]) -> InstallResult:
        """
        Attempt to install an application from raw manifest data.
        """
        logger.info("Attempting to install application...")
        
        try:
            # 1. Parse manifest
            manifest = self._manifest_parser.parse(raw_manifest_data)
            logger.info(f"Parsed manifest for {manifest.id} v{manifest.version}")
            
            # 2. Check if already installed
            if self._registry.get_manifest(manifest.id):
                raise AppInstallError(f"Application {manifest.id} is already installed.")
                
            # 3. Resolve dependencies
            resolved = self._dependency_manager.resolve_dependencies(manifest)
            
            # 4. Grant/Request permissions
            self._permission_manager.grant_permissions(manifest)
            
            # 5. Register application
            self._registry.register(manifest)
            
            logger.info(f"Successfully installed {manifest.id} v{manifest.version}")
            return InstallResult(
                success=True,
                app_id=manifest.id,
                version=manifest.version,
                resolved_dependencies=resolved
            )
            
        except (InvalidManifestError, DependencyResolutionError, AppInstallError) as e:
            logger.error(f"Installation failed: {e}")
            return InstallResult(
                success=False,
                errors=[str(e)]
            )
        except Exception as e:
            logger.error(f"Unexpected error during installation: {e}")
            return InstallResult(
                success=False,
                errors=[f"Unexpected error: {str(e)}"]
            )
