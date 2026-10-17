"""
Asset Manager for registering and tracking media files within a Project Bundle.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bundle import BundleModifier
from .exceptions import AssetNotFoundError, StorageError
from .models import Asset, AssetMetadata, ProjectBundle
from .storage import ProjectStorage
from .versioning import VersioningUtil


class AssetManager:
    """Manages tracking, versioning, and injecting assets into a project bundle."""

    def __init__(self, storage: ProjectStorage) -> None:
        self._storage = storage

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
        """
        Moves a file into the project bundle, versions it if necessary, and registers the Asset metadata.
        """
        project_id = bundle.metadata.project_id
        if not asset_id:
            asset_id = str(uuid.uuid4())
            
        # Figure out the relative destination path and version
        target_dir_path = Path(target_directory)
        base_dest = str(target_dir_path / base_filename).replace("\\", "/")
        
        # Determine existing paths for this directory
        abs_target_dir = Path(self._storage.get_absolute_path(project_id, target_directory))
        existing_paths = []
        if abs_target_dir.exists():
            for f in abs_target_dir.iterdir():
                if f.is_file():
                    existing_paths.append(str(f))
                    
        # Apply versioning
        relative_path, version = VersioningUtil.get_next_versioned_path(base_dest, [Path(p).name for p in existing_paths])
        
        # Store physical file
        try:
            self._storage.store_asset_file(project_id, source_path, relative_path)
        except Exception as e:
            raise StorageError(f"Failed to copy asset into project: {e}") from e
            
        # Create Metadata
        now = datetime.now(timezone.utc).isoformat()
        meta = AssetMetadata(
            asset_id=asset_id,
            asset_type=asset_type,
            created_at=now,
            version=version,
            generation_model=generation_model,
            generation_parameters=generation_parameters or {},
            dependencies=dependencies or []
        )
        
        asset = Asset(
            metadata=meta,
            relative_path=relative_path,
            scene_number=scene_number,
            tags=tags or []
        )
        
        return BundleModifier.add_asset(bundle, asset)

    def get_asset_absolute_path(self, bundle: ProjectBundle, asset_id: str) -> str:
        asset = BundleModifier.get_asset(bundle, asset_id)
        if not asset:
            raise AssetNotFoundError(f"Asset {asset_id} not found in project {bundle.metadata.project_id}")
        return self._storage.get_absolute_path(bundle.metadata.project_id, asset.relative_path)
