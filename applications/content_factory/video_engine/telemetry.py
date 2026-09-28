"""
Telemetry for the Video Engine.
"""

import logging
import time

from core.events.bus import EventBus, Event

logger = logging.getLogger(__name__)


class VideoEngineTelemetry:
    """Publishes telemetry events for the video engine."""
    
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def emit_generation_started(self, project_id: str, fps: int, resolution: str) -> float:
        """Emits an event when rendering starts and returns the current time."""
        event = Event(
            topic="content_factory.video.started",
            source="video_engine",
            payload={
                "project_id": project_id,
                "fps": fps,
                "resolution": resolution
            }
        )
        self._publish(event)
        return time.time()

    def emit_generation_completed(
        self, 
        project_id: str, 
        duration_seconds: float,
        start_time: float
    ) -> None:
        """Emits an event when rendering successfully completes."""
        render_time = time.time() - start_time
        event = Event(
            topic="content_factory.video.completed",
            source="video_engine",
            payload={
                "project_id": project_id,
                "video_duration_seconds": duration_seconds,
                "render_time_seconds": render_time
            }
        )
        self._publish(event)

    def emit_generation_failed(self, project_id: str, error: str) -> None:
        """Emits an event when rendering fails."""
        event = Event(
            topic="content_factory.video.failed",
            source="video_engine",
            payload={
                "project_id": project_id,
                "error": error
            }
        )
        self._publish(event)
        
    def _publish(self, event: Event) -> None:
        try:
            self._event_bus.publish(event)
        except Exception as e:
            logger.debug("Failed to emit telemetry: %s", e)
