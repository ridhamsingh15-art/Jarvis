"""
Capability Facade for the Project Manager.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from core.capability.models import Capability, CapabilityType

from .asset_manager import AssetManager
from .exceptions import ProjectNotFoundError
from .models import ProjectBundle, ProjectBundleMetadata
from .registry import ProjectRegistry
from .storage import ProjectStorage
from .telemetry import ProjectManagerTelemetry
from .validator import ProjectValidator


class ProjectManager:
    """Public facade for managing Project Bundles and their Assets."""

    def __init__(
        self,
        storage: ProjectStorage,
        registry: ProjectRegistry,
        asset_manager: AssetManager,
        validator: ProjectValidator,
        telemetry: ProjectManagerTelemetry
    ) -> None:
        self._storage = storage
        self._registry = registry
        self._asset_manager = asset_manager
        self._validator = validator
        self._telemetry = telemetry
        
        # Hydrate the registry on startup
        self._registry.scan()

    def get_capability_metadata(self) -> Capability:
        return Capability(
            name="project_manager",
            description="Manages Content Factory Project Bundles, Assets, and Versioning.",
            type=CapabilityType.AGENT
        )

    def create_project(self, title: str, tags: list[str] | None = None) -> ProjectBundle:
        project_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        metadata = ProjectBundleMetadata(
            project_id=project_id,
            title=title,
            tags=tags or [],
            created_at=now,
            updated_at=now,
            status="draft"
        )
        
        bundle = ProjectBundle(metadata=metadata)
        
        self._storage.save_bundle(bundle)
        self._registry.register(metadata)
        self._telemetry.emit_project_created(project_id, title)
        
        return bundle

    def get_project(self, project_id: str) -> ProjectBundle:
        bundle = self._storage.load_bundle(project_id)
        if not bundle:
            raise ProjectNotFoundError(f"Project {project_id} not found.")
        return bundle

    def save_project(self, bundle: ProjectBundle) -> None:
        """Validates and saves a project bundle to disk."""
        self._validator.validate(bundle)
        self._storage.save_bundle(bundle)
        self._registry.register(bundle.metadata)
        self._telemetry.emit_project_updated(bundle.metadata.project_id)

    def search_projects(self, title: str = "", tag: str = "") -> list[ProjectBundleMetadata]:
        if title:
            return self._registry.find_by_title(title)
        if tag:
            return self._registry.find_by_tag(tag)
        return self._registry.list_all()

    # Asset Facade methods
    def ingest_asset(
        self,
        bundle: ProjectBundle,
        source_path: str,
        asset_type: str,
        target_directory: str,
        base_filename: str,
        generation_model: str,
        asset_id: str | None = None,
        generation_parameters: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        scene_number: int | None = None,
        tags: list[str] | None = None
    ) -> ProjectBundle:
        
        updated_bundle = self._asset_manager.ingest_asset(
            bundle=bundle,
            source_path=source_path,
            asset_type=asset_type,
            target_directory=target_directory,
            base_filename=base_filename,
            generation_model=generation_model,
            asset_id=asset_id,
            generation_parameters=generation_parameters,
            dependencies=dependencies,
            scene_number=scene_number,
            tags=tags
        )
        self.save_project(updated_bundle)
        
        # Emitting events
        latest_asset = updated_bundle.assets[-1]
        self._telemetry.emit_asset_added(bundle.metadata.project_id, latest_asset.metadata.asset_id, asset_type)
        if latest_asset.metadata.version > 1:
            self._telemetry.emit_asset_versioned(bundle.metadata.project_id, latest_asset.metadata.asset_id, latest_asset.metadata.version)
            
        return updated_bundle
