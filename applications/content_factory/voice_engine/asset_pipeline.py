"""
Asset Pipeline for ingesting voices into the Project Bundle.
"""

import json
from pathlib import Path
import dataclasses

from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.project.manager import ProjectManager
from .models import VoiceMetadata


class VoiceAssetPipeline:
    """Manages writing generated voices to the physical project structure."""
    
    def __init__(self, project_manager: ProjectManager) -> None:
        self._project_manager = project_manager

    def ingest_voice(
        self,
        bundle: ProjectBundle,
        temp_audio_path: str,
        metadata: VoiceMetadata
    ) -> ProjectBundle:
        """
        Saves the binary audio data and its metadata to the bundle's path.
        """
        scene_str = f"scene_{metadata.scene_number:03d}"
        target_dir = f"voices/{scene_str}"
        base_filename = "voice.wav"
        
        params_dict = dataclasses.asdict(metadata.generation_parameters) if hasattr(metadata.generation_parameters, '__dataclass_fields__') else metadata.generation_parameters
        
        updated_bundle = self._project_manager.ingest_asset(
            bundle=bundle,
            source_path=temp_audio_path,
            asset_type="voice",
            target_directory=target_dir,
            base_filename=base_filename,
            generation_model=metadata.model_name,
            generation_parameters=params_dict,
            dependencies=[],
            scene_number=metadata.scene_number,
            tags=["generated_voice", scene_str, metadata.speaker]
        )
        
        latest_asset = updated_bundle.assets[-1]
        
        storage = self._project_manager._storage
        abs_file_path = Path(storage.get_absolute_path(bundle.metadata.project_id, latest_asset.relative_path))
        abs_dir = abs_file_path.parent
        
        # We save a generic metadata.json that describes the latest voice for this scene
        sidecar_path = abs_dir / "metadata.json"
        
        meta_dict = dataclasses.asdict(metadata)
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(meta_dict, f, indent=4)
            
        return updated_bundle
