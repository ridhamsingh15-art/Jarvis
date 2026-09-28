"""
Telemetry for the Analytics Engine.
"""
import time
from core.events.bus import EventBus, Event

class AnalyticsEngineTelemetry:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def emit_started(self, project_id: str) -> float:
        self._publish(Event("content_factory.analytics.sync_started", "analytics_engine", {"project_id": project_id}))
        return time.time()

    def emit_completed(self, project_id: str, start_time: float) -> None:
        self._publish(Event("content_factory.analytics.sync_completed", "analytics_engine", {
            "project_id": project_id,
            "render_time": time.time() - start_time
        }))

    def emit_failed(self, project_id: str, error: str) -> None:
        self._publish(Event("content_factory.analytics.sync_failed", "analytics_engine", {"project_id": project_id, "error": error}))

    def _publish(self, event: Event) -> None:
        try:
            self._event_bus.publish(event)
        except Exception:
            pass
