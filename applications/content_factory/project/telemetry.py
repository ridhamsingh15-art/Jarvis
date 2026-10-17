"""
Telemetry integration for the Project Manager.
"""

from core.events.bus import EventBus
from core.models import Event


class ProjectManagerTelemetry:
    """Publishes execution telemetry to the global EventBus."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def emit_project_created(self, project_id: str, title: str) -> None:
        self._event_bus.publish(Event(
            topic="ProjectBundleCreated",
            payload={"project_id": project_id, "title": title},
            source="project_manager"
        ))

    def emit_project_updated(self, project_id: str) -> None:
        self._event_bus.publish(Event(
            topic="ProjectBundleUpdated",
            payload={"project_id": project_id},
            source="project_manager"
        ))

    def emit_asset_added(self, project_id: str, asset_id: str, asset_type: str) -> None:
        self._event_bus.publish(Event(
            topic="ProjectAssetAdded",
            payload={"project_id": project_id, "asset_id": asset_id, "asset_type": asset_type},
            source="project_manager"
        ))
        
    def emit_asset_versioned(self, project_id: str, asset_id: str, version: int) -> None:
        self._event_bus.publish(Event(
            topic="ProjectAssetVersioned",
            payload={"project_id": project_id, "asset_id": asset_id, "version": version},
            source="project_manager"
        ))
