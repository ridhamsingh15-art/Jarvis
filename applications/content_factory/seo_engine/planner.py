"""
Planner for the SEO Engine.
"""
import os
import json
import dataclasses
from pathlib import Path

from applications.content_factory.project.models import ProjectBundle, ProjectBundleMetadata
from applications.content_factory.project.manager import ProjectManager

from .generator import SEOGenerator
from .telemetry import SEOEngineTelemetry
from .models import SEOAssetMetadata
from .exceptions import SEOEngineError

class SEOGenerationPlanner:
    def __init__(
        self,
        generator: SEOGenerator,
        project_manager: ProjectManager,
        telemetry: SEOEngineTelemetry
    ) -> None:
        self._generator = generator
        self._project_manager = project_manager
        self._telemetry = telemetry

    def execute(self, bundle: ProjectBundle) -> ProjectBundle:
        if not bundle.storyboard_package:
            raise SEOEngineError("No storyboard package found.")
            
        start_time = self._telemetry.emit_started(bundle.metadata.project_id)
        
        try:
            title = bundle.storyboard_package.script_title or "Untitled"
            description = "A generated video."
            
            seo_json_str = self._generator.generate(title, description)
            seo_data = json.loads(seo_json_str)
            
            import tempfile
            fd, temp_path = tempfile.mkstemp(suffix=".json")
            os.write(fd, seo_json_str.encode('utf-8'))
            os.close(fd)
            
            updated_bundle = self._project_manager.ingest_asset(
                bundle=bundle,
                source_path=temp_path,
                asset_type="seo",
                target_directory="seo",
                base_filename="youtube_seo.json",
                generation_model="mock_seo",
                generation_parameters={},
                dependencies=[],
                scene_number=0,
                tags=["youtube"]
            )
            
            meta = SEOAssetMetadata(
                title_length=len(seo_data["youtube_title"]),
                tags_count=len(seo_data["tags"])
            )
            latest_asset = updated_bundle.assets[-1]
            storage = self._project_manager._storage
            abs_file_path = Path(storage.get_absolute_path(bundle.metadata.project_id, latest_asset.relative_path))
            
            with open(abs_file_path.parent / "metadata.json", "w") as f:
                json.dump(dataclasses.asdict(meta), f, indent=4)
                
            os.remove(temp_path)
            
            # Inject directly into ProjectBundleMetadata
            from applications.content_factory.project.bundle import BundleModifier
            updated_metadata = dataclasses.replace(updated_bundle.metadata, seo_metadata=seo_data)
            updated_bundle = dataclasses.replace(updated_bundle, metadata=updated_metadata)
            
            self._telemetry.emit_completed(bundle.metadata.project_id, start_time)
            
            return updated_bundle
            
        except Exception as e:
            self._telemetry.emit_failed(bundle.metadata.project_id, str(e))
            raise SEOEngineError(f"Generation failed: {e}")
