"""
Telemetry integration for the Storyboard Engine.
"""

from core.events.bus import EventBus
from core.models import Event


class StoryboardEngineTelemetry:
    """Publishes execution telemetry to the global EventBus."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def emit_storyboard_started(self, title: str, mission_id: str) -> None:
        self._event_bus.publish(Event(
            topic="StoryboardGenerationStarted",
            payload={"script_title": title, "mission_id": mission_id},
            source="storyboard_engine"
        ))

    def emit_storyboard_finished(self, title: str, mission_id: str, duration: float, scene_count: int) -> None:
        self._event_bus.publish(Event(
            topic="StoryboardGenerationFinished",
            payload={"script_title": title, "mission_id": mission_id, "duration": duration, "scene_count": scene_count},
            source="storyboard_engine"
        ))

    def emit_storyboard_failed(self, mission_id: str, error: str) -> None:
        self._event_bus.publish(Event(
            topic="StoryboardGenerationFailed",
            payload={"mission_id": mission_id, "error": error},
            source="storyboard_engine"
        ))

    def emit_validation_failed(self, mission_id: str, reasons: list[str]) -> None:
        self._event_bus.publish(Event(
            topic="StoryboardValidationFailed",
            payload={"mission_id": mission_id, "reasons": reasons},
            source="storyboard_engine"
        ))
