"""
Planner for the Thumbnail Engine.
"""
import os
import json
import dataclasses
from pathlib import Path

from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.project.manager import ProjectManager

from .generator import ThumbnailGenerator
from .telemetry import ThumbnailEngineTelemetry
from .models import ThumbnailGenerationRequest, ThumbnailAssetMetadata
from .exceptions import ThumbnailEngineError

class ThumbnailGenerationPlanner:
    def __init__(
        self,
        generator: ThumbnailGenerator,
        project_manager: ProjectManager,
        telemetry: ThumbnailEngineTelemetry
    ) -> None:
        self._generator = generator
        self._project_manager = project_manager
        self._telemetry = telemetry

    def execute(self, bundle: ProjectBundle) -> ProjectBundle:
        if not bundle.storyboard_package:
            raise ThumbnailEngineError("No storyboard package found.")
            
        start_time = self._telemetry.emit_started(bundle.metadata.project_id)
        
        try:
            # Find an image asset flagged as thumbnail candidate, or just use the first image
            base_image = None
            for asset in bundle.assets:
                if asset.metadata.asset_type == "image":
                    base_image = asset
                    # If we can figure out if it was a thumbnail candidate from storyboard, great.
                    # For now, just grab the first available image.
                    break
                    
            if not base_image:
                raise ThumbnailEngineError("No image assets found to generate thumbnail from.")
                
            req = ThumbnailGenerationRequest(
                base_image_path=base_image.relative_path,
                title_text=bundle.storyboard_package.script_title,
                layout_style="youtube_standard"
            )
            
            thumb_bytes = self._generator.generate(req)
            
            import tempfile
            fd, temp_path = tempfile.mkstemp(suffix=".jpg")
            os.write(fd, thumb_bytes)
            os.close(fd)
            
            updated_bundle = self._project_manager.ingest_asset(
                bundle=bundle,
                source_path=temp_path,
                asset_type="thumbnail",
                target_directory="thumbnails",
                base_filename="thumbnail.jpg",
                generation_model="mock_thumbnail",
                generation_parameters=dataclasses.asdict(req),
                dependencies=[base_image.metadata.asset_id],
                scene_number=0,
                tags=["youtube", "final"]
            )
            
            meta = ThumbnailAssetMetadata(layout=req.layout_style, has_text=bool(req.title_text))
            latest_asset = updated_bundle.assets[-1]
            storage = self._project_manager._storage
            abs_file_path = Path(storage.get_absolute_path(bundle.metadata.project_id, latest_asset.relative_path))
            
            with open(abs_file_path.parent / "metadata.json", "w") as f:
                json.dump(dataclasses.asdict(meta), f, indent=4)
                
            os.remove(temp_path)
            self._telemetry.emit_completed(bundle.metadata.project_id, start_time)
            
            return updated_bundle
            
        except Exception as e:
            self._telemetry.emit_failed(bundle.metadata.project_id, str(e))
            raise ThumbnailEngineError(f"Generation failed: {e}")
