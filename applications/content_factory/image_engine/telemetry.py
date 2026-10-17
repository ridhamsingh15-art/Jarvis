"""
Telemetry integration for the Image Generation Engine.
"""

from core.events.bus import EventBus
from core.models import Event


class ImageEngineTelemetry:
    """Publishes execution telemetry to the global EventBus."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def emit_generation_queued(self, project_id: str, scene_number: int, model: str) -> None:
        self._event_bus.publish(Event(
            topic="ImageGenerationQueued",
            payload={"project_id": project_id, "scene_number": scene_number, "model": model},
            source="image_engine"
        ))

    def emit_generation_started(self, project_id: str, scene_number: int, model: str) -> None:
        self._event_bus.publish(Event(
            topic="ImageGenerationStarted",
            payload={"project_id": project_id, "scene_number": scene_number, "model": model},
            source="image_engine"
        ))

    def emit_generation_completed(self, project_id: str, scene_number: int, duration: float) -> None:
        self._event_bus.publish(Event(
            topic="ImageGenerationCompleted",
            payload={"project_id": project_id, "scene_number": scene_number, "duration": duration},
            source="image_engine"
        ))

    def emit_generation_failed(self, project_id: str, scene_number: int, error: str) -> None:
        self._event_bus.publish(Event(
            topic="ImageGenerationFailed",
            payload={"project_id": project_id, "scene_number": scene_number, "error": error},
            source="image_engine"
        ))

    def emit_quality_retry(self, project_id: str, scene_number: int, score: float, attempt: int) -> None:
        self._event_bus.publish(Event(
            topic="ImageGenerationRetry",
            payload={"project_id": project_id, "scene_number": scene_number, "score": score, "attempt": attempt},
            source="image_engine"
        ))
