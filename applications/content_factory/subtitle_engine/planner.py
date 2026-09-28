"""
Planner for the Subtitle Engine.
"""
import os
import json
import dataclasses
from pathlib import Path

from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.project.manager import ProjectManager

from .generator import SubtitleGenerator
from .telemetry import SubtitleEngineTelemetry
from .models import SubtitleGenerationRequest, SubtitleAssetMetadata
from .exceptions import SubtitleEngineError

class SubtitleGenerationPlanner:
    def __init__(
        self,
        generator: SubtitleGenerator,
        project_manager: ProjectManager,
        telemetry: SubtitleEngineTelemetry
    ) -> None:
        self._generator = generator
        self._project_manager = project_manager
        self._telemetry = telemetry

    def execute(self, bundle: ProjectBundle) -> ProjectBundle:
        if not bundle.storyboard_package:
            raise SubtitleEngineError("No storyboard package found.")
            
        start_time = self._telemetry.emit_started(bundle.metadata.project_id)
        
        try:
            requests = []
            current_time = 0.0
            for scene in bundle.storyboard_package.scenes:
                text = scene.dialogue or scene.narration
                if text:
                    requests.append(SubtitleGenerationRequest(
                        text=text,
                        start_time=current_time,
                        end_time=current_time + scene.duration,
                        speaker="Narrator" if scene.narration else "Character"
                    ))
                current_time += scene.duration
                
            srt_content = self._generator.generate_srt(requests)
            
            import tempfile
            fd, temp_path = tempfile.mkstemp(suffix=".srt")
            os.write(fd, srt_content.encode('utf-8'))
            os.close(fd)
            
            updated_bundle = self._project_manager.ingest_asset(
                bundle=bundle,
                source_path=temp_path,
                asset_type="subtitle",
                target_directory="subtitles",
                base_filename="subs.srt",
                generation_model="local_srt",
                generation_parameters={"format": "srt"},
                dependencies=[],
                scene_number=0,
                tags=["srt", "full_video"]
            )
            
            meta = SubtitleAssetMetadata(format="srt", total_segments=len(requests))
            latest_asset = updated_bundle.assets[-1]
            storage = self._project_manager._storage
            abs_file_path = Path(storage.get_absolute_path(bundle.metadata.project_id, latest_asset.relative_path))
            
            with open(abs_file_path.parent / "metadata.json", "w") as f:
                json.dump(dataclasses.asdict(meta), f, indent=4)
                
            os.remove(temp_path)
            self._telemetry.emit_completed(bundle.metadata.project_id, "srt", start_time)
            
            return updated_bundle
            
        except Exception as e:
            self._telemetry.emit_failed(bundle.metadata.project_id, str(e))
            raise SubtitleEngineError(f"Generation failed: {e}")
