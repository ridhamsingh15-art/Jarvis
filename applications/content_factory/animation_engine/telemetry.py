"""
Telemetry for the Animation Engine.
"""

import logging
import time
from typing import Dict, Any

from core.events.bus import EventBus, Event

logger = logging.getLogger(__name__)


class AnimationEngineTelemetry:
    """Publishes telemetry events for the animation engine."""
    
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def emit_generation_started(self, project_id: str, scene_number: int, model_name: str) -> float:
        """Emits an event when generation starts and returns the current time."""
        event = Event(
            topic="content_factory.animation.started",
            source="animation_engine",
            payload={
                "project_id": project_id,
                "scene_number": scene_number,
                "model_name": model_name
            }
        )
        self._publish(event)
        return time.time()

    def emit_generation_completed(
        self, 
        project_id: str, 
        scene_number: int, 
        model_name: str, 
        start_time: float,
        quality_score: float,
        retry_count: int
    ) -> None:
        """Emits an event when generation successfully completes."""
        duration = time.time() - start_time
        event = Event(
            topic="content_factory.animation.completed",
            source="animation_engine",
            payload={
                "project_id": project_id,
                "scene_number": scene_number,
                "model_name": model_name,
                "duration_seconds": duration,
                "quality_score": quality_score,
                "retry_count": retry_count
            }
        )
        self._publish(event)

    def emit_generation_failed(self, project_id: str, scene_number: int, model_name: str, error: str) -> None:
        """Emits an event when generation fails completely."""
        event = Event(
            topic="content_factory.animation.failed",
            source="animation_engine",
            payload={
                "project_id": project_id,
                "scene_number": scene_number,
                "model_name": model_name,
                "error": error
            }
        )
        self._publish(event)
        
    def _publish(self, event: Event) -> None:
        try:
            self._event_bus.publish(event)
        except Exception as e:
            logger.debug("Failed to emit telemetry: %s", e)
