"""
Planner for the Analytics Engine.
"""
import dataclasses
from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.project.manager import ProjectManager

from .tracker import AnalyticsTracker
from .telemetry import AnalyticsEngineTelemetry
from .models import AnalyticsSyncRequest
from .exceptions import AnalyticsEngineError

class AnalyticsPlanner:
    def __init__(
        self,
        tracker: AnalyticsTracker,
        project_manager: ProjectManager,
        telemetry: AnalyticsEngineTelemetry
    ) -> None:
        self._tracker = tracker
        self._project_manager = project_manager
        self._telemetry = telemetry

    def execute(self, bundle: ProjectBundle, request: AnalyticsSyncRequest) -> ProjectBundle:
        if bundle.metadata.publishing_status not in ["published", "scheduled"]:
            raise AnalyticsEngineError("Project must be published to sync analytics.")
            
        start_time = self._telemetry.emit_started(bundle.metadata.project_id)
        
        try:
            metrics = self._tracker.fetch_metrics(bundle, request)
            
            # Update analytics dict in ProjectBundle
            current_analytics = dict(bundle.analytics)
            current_analytics.update(metrics)
            
            updated_bundle = dataclasses.replace(bundle, analytics=current_analytics)
            
            self._telemetry.emit_completed(bundle.metadata.project_id, start_time)
            return updated_bundle
            
        except Exception as e:
            self._telemetry.emit_failed(bundle.metadata.project_id, str(e))
            raise AnalyticsEngineError(f"Analytics sync failed: {e}")
