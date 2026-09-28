"""
Planner for the Video Engine.
"""

import logging
import uuid
import os
import datetime
import dataclasses
import json
from pathlib import Path

from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.project.manager import ProjectManager

from .renderer import VideoRenderer
from .assembler import SceneSequencer
from .validator import VideoValidator
from .telemetry import VideoEngineTelemetry
from .models import VideoParameters, VideoMetadata
from .exceptions import VideoEngineError

logger = logging.getLogger(__name__)


class VideoGenerationPlanner:
    """Orchestrates timeline building, rendering, and asset storage."""

    def __init__(
        self,
        renderer: VideoRenderer,
        sequencer: SceneSequencer,
        validator: VideoValidator,
        project_manager: ProjectManager,
        telemetry: VideoEngineTelemetry
    ) -> None:
        self._renderer = renderer
        self._sequencer = sequencer
        self._validator = validator
        self._project_manager = project_manager
        self._telemetry = telemetry

    def execute(self, bundle: ProjectBundle, params: VideoParameters) -> ProjectBundle:
        """Plans and executes video generation for the given bundle."""
        if not bundle.storyboard_package:
            raise VideoEngineError("No storyboard package found in bundle.")
            
        task_id = str(uuid.uuid4())
        
        try:
            # 1. Assemble Timeline
            task = self._sequencer.assemble(task_id, bundle, params)
        except Exception as e:
            self._telemetry.emit_generation_failed(bundle.metadata.project_id, f"Timeline assembly failed: {e}")
            raise VideoEngineError(f"Timeline assembly failed: {e}")
            
        start_time = self._telemetry.emit_generation_started(
            bundle.metadata.project_id, params.fps, params.resolution
        )
        
        try:
            # 2. Render
            video_data = self._renderer.render(task)
            
            # Write to temp file
            import tempfile
            fd, temp_path = tempfile.mkstemp(suffix=".mp4")
            os.write(fd, video_data)
            os.close(fd)
            
            # Calculate final duration
            duration = sum(clip.duration for clip in task.clips)
            
            # 3. Create Metadata
            meta = VideoMetadata(
                resolution=params.resolution,
                fps=params.fps,
                codec=params.codec,
                bitrate=params.bitrate,
                duration_seconds=duration,
                generation_parameters=dataclasses.asdict(params),
                version=1,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
            
            self._validator.validate_metadata(meta)
            
            # 4. Ingest Asset
            updated_bundle = self._project_manager.ingest_asset(
                bundle=bundle,
                source_path=temp_path,
                asset_type="video",
                target_directory="exports",
                base_filename="video.mp4",
                generation_model="ffmpeg",
                generation_parameters=meta.generation_parameters,
                dependencies=[],
                scene_number=0,  # 0 indicates full project
                tags=["final_video"]
            )
            
            # Save sidecar metadata
            latest_asset = updated_bundle.assets[-1]
            storage = self._project_manager._storage
            abs_file_path = Path(storage.get_absolute_path(bundle.metadata.project_id, latest_asset.relative_path))
            sidecar_path = abs_file_path.parent / "metadata.json"
            
            with open(sidecar_path, "w", encoding="utf-8") as f:
                json.dump(dataclasses.asdict(meta), f, indent=4)
                
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            self._telemetry.emit_generation_completed(
                bundle.metadata.project_id, duration, start_time
            )
            return updated_bundle
            
        except Exception as e:
            self._telemetry.emit_generation_failed(bundle.metadata.project_id, str(e))
            raise VideoEngineError(f"Video generation failed: {e}")
