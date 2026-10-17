"""
Telemetry integration for the Script Engine.
"""

from core.events.bus import EventBus
from core.models import Event


class ScriptEngineTelemetry:
    """Publishes execution telemetry to the global EventBus."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def emit_script_started(self, topic: str, mission_id: str) -> None:
        self._event_bus.publish(Event(
            topic="ScriptGenerationStarted",
            payload={"script_topic": topic, "mission_id": mission_id},
            source="script_engine"
        ))

    def emit_script_finished(self, title: str, mission_id: str, duration: float) -> None:
        self._event_bus.publish(Event(
            topic="ScriptGenerationFinished",
            payload={"title": title, "mission_id": mission_id, "duration": duration},
            source="script_engine"
        ))

    def emit_script_failed(self, mission_id: str, error: str) -> None:
        self._event_bus.publish(Event(
            topic="ScriptGenerationFailed",
            payload={"mission_id": mission_id, "error": error},
            source="script_engine"
        ))

    def emit_validation_failed(self, mission_id: str, reasons: list[str]) -> None:
        self._event_bus.publish(Event(
            topic="ScriptValidationFailed",
            payload={"mission_id": mission_id, "reasons": reasons},
            source="script_engine"
        ))
