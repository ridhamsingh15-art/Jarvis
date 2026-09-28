import builtins
import os

from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from core.telemetry import AsyncLogger

from .exceptions import PackageError
from .interfaces import (
    DependencyResolver,
    PackageCache,
    PackageDownloader,
    PackageInstaller,
    PackageRepository,
    RollbackManager,
    SignatureVerifier,
)
from .models import PackageMetadata, RepositoryConfig
from .rollback import DefaultRollbackManager


class PackageManager(RuntimeComponent):
    """Orchestrates the Package Manager subsystem."""

    def __init__(
        self,
        repositories: builtins.list[PackageRepository],
        downloader: PackageDownloader,
        resolver: DependencyResolver,
        verifier: SignatureVerifier,
        cache: PackageCache,
        installer: PackageInstaller,
        rollback_manager: RollbackManager,
        event_bus: EventBus,
        logger: AsyncLogger,
        install_dir: str
    ) -> None:
        self._repositories = repositories
        self._downloader = downloader
        self._resolver = resolver
        self._verifier = verifier
        self._cache = cache
        self._installer = installer
        self._rollback = rollback_manager
        self._event_bus = event_bus
        self._logger = logger
        self._install_dir = install_dir
        
        # In-memory track of installed metadata for dependency resolution context
        self._installed: dict[str, PackageMetadata] = {}
        
        self._state = ComponentState.INITIALIZED
        self._metadata = ComponentMetadata(
            id="core.packages",
            name="Package Manager System",
            version="1.0.0",
            dependencies=["core.events", "core.telemetry"]
        )

    @property
    def metadata(self) -> ComponentMetadata:
        return self._metadata

    @property
    def state(self) -> ComponentState:
        return self._state

    async def start(self) -> None:
        if self._state in (ComponentState.STARTING, ComponentState.RUNNING):
            return

        self._state = ComponentState.STARTING
        self._logger.info("Starting Package Manager System...")
        os.makedirs(self._install_dir, exist_ok=True)
        self._state = ComponentState.RUNNING
        self._logger.info("Package Manager System started successfully.")

    async def stop(self) -> None:
        if self._state != ComponentState.RUNNING:
            return

        self._state = ComponentState.STOPPING
        self._logger.info("Stopping Package Manager System...")
        self._state = ComponentState.STOPPED
        self._logger.info("Package Manager System stopped.")

    async def health(self) -> HealthReport:
        try:
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.HEALTHY,
                details={"installed_packages": len(self._installed)}
            )
        except Exception as e:  # noqa: BLE001
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.UNHEALTHY,
                error=str(e)
            )

    def add_repository(self, repository: PackageRepository) -> None:
        self._repositories.append(repository)

    def _fetch_metadata(self, package_id: Identifier, version: str | None = None) -> PackageMetadata:
        for repo in self._repositories:
            try:
                meta = repo.fetch_metadata(package_id, version)
                if meta:
                    return meta
            except Exception:  # noqa: BLE001, S112
                continue
        raise PackageError(f"Package {package_id.value} not found in any repository.")

    def install(self, package_id: Identifier, version: str | None = None) -> None:
        """Installs a package and its dependencies."""
        self._logger.info(f"Initiating installation of {package_id.value}")
        
        # 1. Fetch metadata
        meta = self._fetch_metadata(package_id, version)
        
        # 2. Resolve dependencies
        packages_to_install = [meta]
        # In a real system, you'd fetch metadata for all dependencies recursively
        resolved = self._resolver.resolve(packages_to_install)
        
        for pkg_meta in resolved:
            self._install_single(pkg_meta)

    def _install_single(self, meta: PackageMetadata) -> None:
        target_dir = os.path.join(self._install_dir, meta.id.value)
        
        # Check cache
        cache_entry = self._cache.get(meta.id, meta.version)
        if not cache_entry:
            # Download
            # For simplicity we mock the repository config here
            from .enums import RepositoryType
            repo_config = RepositoryConfig(name="default", url="http://mock", type=RepositoryType.HTTP)
            temp_path = os.path.join(self._install_dir, f"{meta.id.value}_{meta.version}.zip")
            downloaded_path = self._downloader.download(meta, repo_config, temp_path)
            
            # Verify
            self._verifier.verify(downloaded_path, meta)
            
            # Cache
            cache_entry = self._cache.put(meta.id, meta.version, downloaded_path)
            
        # Backup existing if it's an update
        backup_path = None
        if isinstance(self._rollback, DefaultRollbackManager):
            backup_path = self._rollback.backup_existing(meta.id, target_dir)

        try:
            # Install
            self._installer.install(cache_entry, target_dir)
            self._installed[meta.id.value] = meta
            
            # Create receipt
            self._rollback.create_receipt(meta.id, meta.version, backup_path)
            
            self._publish_event("package.installed", meta.id, meta.version)
            self._logger.info(f"Successfully installed {meta.id.value} {meta.version}")
        except Exception as e:  # noqa: BLE001
            # Revert if backup exists
            if backup_path:
                try:
                    import shutil
                    if os.path.exists(target_dir):
                        shutil.rmtree(target_dir)
                    os.rename(backup_path, target_dir)
                except Exception as revert_e:  # noqa: BLE001
                    self._logger.error(f"Failed to revert {meta.id.value}: {revert_e}")
            raise PackageError(f"Installation of {meta.id.value} failed: {e}")

    def update(self, package_id: Identifier) -> None:
        """Updates a package to the latest available version."""
        # For simplicity, passing None to version fetches the latest
        self.install(package_id, version=None)
        self._publish_event("package.updated", package_id, "latest")

    def remove(self, package_id: Identifier) -> None:
        """Uninstalls a package."""
        target_dir = os.path.join(self._install_dir, package_id.value)
        self._installer.uninstall(package_id, target_dir)
        if package_id.value in self._installed:
            del self._installed[package_id.value]
        self._publish_event("package.removed", package_id, "any")
        self._logger.info(f"Successfully removed {package_id.value}")

    def rollback(self, package_id: Identifier) -> None:
        """Rolls back a package to its previous state."""
        receipt = self._rollback.get_receipt(package_id)
        if not receipt:
            raise PackageError(f"No installation receipt found for {package_id.value}")
            
        target_dir = os.path.join(self._install_dir, package_id.value)
        self._rollback.rollback(receipt, target_dir)
        
        self._publish_event("package.rollback", package_id, receipt.version)
        self._logger.info(f"Successfully rolled back {package_id.value}")

    def list_packages(self) -> builtins.list[PackageMetadata]:
        return builtins.list(self._installed.values())

    def _publish_event(self, topic: str, package_id: Identifier, version: str) -> None:
        event = Event(
            topic=topic,
            payload={"package_id": package_id.value, "version": version},
            source=self.metadata.id
        )
        self._event_bus.publish(event)
