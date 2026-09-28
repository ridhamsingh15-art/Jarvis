"""
Bridges the Image Generator and the Project Manager to store assets physically.
"""

import json
from pathlib import Path

from applications.content_factory.project.manager import ProjectManager
from applications.content_factory.project.models import ProjectBundle

from .models import ImageMetadata


class AssetPipeline:
    """Ingests generated images into the central Project Bundle."""

    def __init__(self, project_manager: ProjectManager) -> None:
        self._project_manager = project_manager

    def ingest_image(
        self, 
        bundle: ProjectBundle, 
        temp_image_path: str, 
        metadata: ImageMetadata
    ) -> ProjectBundle:
        """
        Moves the temporary image into the project bundle under images/scene_XXX/,
        saves a sidecar metadata.json, and registers the asset in the ProjectBundle manifest.
        """
        scene_str = f"scene_{metadata.scene_number:03d}"
        target_dir = f"images/{scene_str}"
        base_filename = "image.png"
        
        # Ingest into the bundle (AssetManager handles versioning)
        import dataclasses
        params_dict = dataclasses.asdict(metadata.generation_parameters) if hasattr(metadata.generation_parameters, '__dataclass_fields__') else metadata.generation_parameters
        
        updated_bundle = self._project_manager.ingest_asset(
            bundle=bundle,
            source_path=temp_image_path,
            asset_type="image",
            target_directory=target_dir,
            base_filename=base_filename,
            generation_model=metadata.generation_model,
            generation_parameters=params_dict,
            dependencies=[],
            scene_number=metadata.scene_number,
            tags=["generated_image", scene_str]
        )
        
        # Write sidecar metadata.json in that same directory
        # We need the absolute path to the directory we just wrote to
        # The new asset is the last one in the list
        latest_asset = updated_bundle.assets[-1]
        
        # Hack to access storage securely through project manager
        # In a real system, ProjectManager would expose a method to get absolute dir path
        # We know relative_path is something like images/scene_001/image_v2.png
        storage = self._project_manager._storage
        abs_file_path = Path(storage.get_absolute_path(bundle.metadata.project_id, latest_asset.relative_path))
        abs_dir = abs_file_path.parent
        
        # Save sidecar
        sidecar_path = abs_dir / "metadata.json"
        
        # We merge the existing sidecar data if it exists, but for simplicity we overwrite with the latest version's metadata
        meta_dict = dataclasses.asdict(metadata)
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(meta_dict, f, indent=2)
            
        return updated_bundle
