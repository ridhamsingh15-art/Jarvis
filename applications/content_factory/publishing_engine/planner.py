"""
Planner for the Publishing Engine.
"""
import dataclasses
from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.project.manager import ProjectManager

from .adapter import PublishingAdapter
from .telemetry import PublishingEngineTelemetry
from .models import PublishRequest
from .exceptions import PublishingEngineError

class PublishingPlanner:
    def __init__(
        self,
        adapter: PublishingAdapter,
        project_manager: ProjectManager,
        telemetry: PublishingEngineTelemetry
    ) -> None:
        self._adapter = adapter
        self._project_manager = project_manager
        self._telemetry = telemetry

    def execute(self, bundle: ProjectBundle, request: PublishRequest) -> ProjectBundle:
        if not bundle.metadata.seo_metadata:
            raise PublishingEngineError("No SEO metadata found in bundle. Must run SEO Engine first.")
            
        start_time = self._telemetry.emit_started(bundle.metadata.project_id)
        
        try:
            success = self._adapter.publish(bundle, request)
            if not success:
                raise PublishingEngineError("n8n workflow failed.")
                
            from applications.content_factory.project.bundle import BundleModifier
            status = "published" if request.mode == "immediate" else "scheduled" if request.mode == "scheduled" else "draft"
            
            updated_metadata = dataclasses.replace(bundle.metadata, publishing_status=status)
            updated_bundle = dataclasses.replace(bundle, metadata=updated_metadata)
            
            self._telemetry.emit_completed(bundle.metadata.project_id, status, start_time)
            
            return updated_bundle
            
        except Exception as e:
            self._telemetry.emit_failed(bundle.metadata.project_id, str(e))
            raise PublishingEngineError(f"Publishing failed: {e}")
