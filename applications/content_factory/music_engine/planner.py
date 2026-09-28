"""
Planner for the Music Engine.
"""

import os
import json
import dataclasses
from pathlib import Path

from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.project.manager import ProjectManager

from .generator import MusicGenerator
from .telemetry import MusicEngineTelemetry
from .models import MusicGenerationRequest, MusicAssetMetadata
from .exceptions import MusicEngineError

class MusicGenerationPlanner:
    def __init__(
        self,
        generator: MusicGenerator,
        project_manager: ProjectManager,
        telemetry: MusicEngineTelemetry
    ) -> None:
        self._generator = generator
        self._project_manager = project_manager
        self._telemetry = telemetry

    def execute(self, bundle: ProjectBundle) -> ProjectBundle:
        if not bundle.storyboard_package:
            raise MusicEngineError("No storyboard package found.")
            
        start_time = self._telemetry.emit_started(bundle.metadata.project_id)
        
        try:
            # We'll generate a single background track for the whole video based on mood
            total_duration = sum(s.duration for s in bundle.storyboard_package.scenes)
            mood = bundle.storyboard_package.scenes[0].mood if bundle.storyboard_package.scenes else "neutral"
            
            req = MusicGenerationRequest(prompt=f"{mood} background music", duration_seconds=total_duration, mood=mood)
            audio_bytes = self._generator.generate(req)
            
            import tempfile
            fd, temp_path = tempfile.mkstemp(suffix=".wav")
            os.write(fd, audio_bytes)
            os.close(fd)
            
            updated_bundle = self._project_manager.ingest_asset(
                bundle=bundle,
                source_path=temp_path,
                asset_type="music",
                target_directory="music",
                base_filename="background.wav",
                generation_model="mock_music",
                generation_parameters=dataclasses.asdict(req),
                dependencies=[],
                scene_number=0,
                tags=["background"]
            )
            
            meta = MusicAssetMetadata(duration=total_duration, prompt=req.prompt, model="mock_music")
            latest_asset = updated_bundle.assets[-1]
            storage = self._project_manager._storage
            abs_file_path = Path(storage.get_absolute_path(bundle.metadata.project_id, latest_asset.relative_path))
            
            with open(abs_file_path.parent / "metadata.json", "w") as f:
                json.dump(dataclasses.asdict(meta), f, indent=4)
                
            os.remove(temp_path)
            self._telemetry.emit_completed(bundle.metadata.project_id, total_duration, start_time)
            
            return updated_bundle
            
        except Exception as e:
            self._telemetry.emit_failed(bundle.metadata.project_id, str(e))
            raise MusicEngineError(f"Generation failed: {e}")
