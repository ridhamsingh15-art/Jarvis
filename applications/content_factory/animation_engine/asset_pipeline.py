"""
Asset Pipeline for ingesting animations into the Project Bundle.
"""

import json
from pathlib import Path
import tempfile
import os
import dataclasses

from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.project.manager import ProjectManager
from .models import AnimationMetadata


class AnimationAssetPipeline:
    """Manages writing generated animations to the physical project structure."""
    
    def __init__(self, project_manager: ProjectManager) -> None:
        self._project_manager = project_manager

    def ingest_animation(
        self,
        bundle: ProjectBundle,
        temp_animation_path: str,
        metadata: AnimationMetadata
    ) -> ProjectBundle:
        """
        Saves the binary animation data and its metadata to the bundle's path.
        """
        scene_str = f"scene_{metadata.scene_number:03d}"
        target_dir = f"animations/{scene_str}"
        base_filename = "clip.mp4"
        
        params_dict = dataclasses.asdict(metadata.generation_parameters) if hasattr(metadata.generation_parameters, '__dataclass_fields__') else metadata.generation_parameters
        
        updated_bundle = self._project_manager.ingest_asset(
            bundle=bundle,
            source_path=temp_animation_path,
            asset_type="animation",
            target_directory=target_dir,
            base_filename=base_filename,
            generation_model=metadata.model_name,
            generation_parameters=params_dict,
            dependencies=[],
            scene_number=metadata.scene_number,
            tags=["generated_animation", scene_str]
        )
        
        latest_asset = updated_bundle.assets[-1]
        
        storage = self._project_manager._storage
        abs_file_path = Path(storage.get_absolute_path(bundle.metadata.project_id, latest_asset.relative_path))
        abs_dir = abs_file_path.parent
        
        sidecar_path = abs_dir / "metadata.json"
        
        meta_dict = dataclasses.asdict(metadata)
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(meta_dict, f, indent=4)
            
        return updated_bundle
