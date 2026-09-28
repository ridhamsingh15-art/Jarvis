"""
Telemetry for the SEO Engine.
"""
import time
from core.events.bus import EventBus, Event

class SEOEngineTelemetry:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def emit_started(self, project_id: str) -> float:
        self._publish(Event("content_factory.seo.started", "seo_engine", {"project_id": project_id}))
        return time.time()

    def emit_completed(self, project_id: str, start_time: float) -> None:
        self._publish(Event("content_factory.seo.completed", "seo_engine", {
            "project_id": project_id,
            "render_time": time.time() - start_time
        }))

    def emit_failed(self, project_id: str, error: str) -> None:
        self._publish(Event("content_factory.seo.failed", "seo_engine", {"project_id": project_id, "error": error}))

    def _publish(self, event: Event) -> None:
        try:
            self._event_bus.publish(event)
        except Exception:
            pass
