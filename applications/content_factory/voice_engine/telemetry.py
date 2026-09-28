"""
Telemetry for the Voice Engine.
"""

import logging
import time
from typing import Dict, Any

from core.events.bus import EventBus, Event

logger = logging.getLogger(__name__)


class VoiceEngineTelemetry:
    """Publishes telemetry events for the voice engine."""
    
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def emit_generation_started(self, project_id: str, scene_number: int, model_name: str, speaker: str) -> float:
        """Emits an event when generation starts and returns the current time."""
        event = Event(
            topic="content_factory.voice.started",
            source="voice_engine",
            payload={
                "project_id": project_id,
                "scene_number": scene_number,
                "model_name": model_name,
                "speaker": speaker
            }
        )
        self._publish(event)
        return time.time()

    def emit_generation_completed(
        self, 
        project_id: str, 
        scene_number: int, 
        model_name: str,
        speaker: str,
        start_time: float,
        quality_score: float,
        retry_count: int
    ) -> None:
        """Emits an event when generation successfully completes."""
        duration = time.time() - start_time
        event = Event(
            topic="content_factory.voice.completed",
            source="voice_engine",
            payload={
                "project_id": project_id,
                "scene_number": scene_number,
                "model_name": model_name,
                "speaker": speaker,
                "duration_seconds": duration,
                "quality_score": quality_score,
                "retry_count": retry_count
            }
        )
        self._publish(event)

    def emit_generation_failed(self, project_id: str, scene_number: int, model_name: str, speaker: str, error: str) -> None:
        """Emits an event when generation fails completely."""
        event = Event(
            topic="content_factory.voice.failed",
            source="voice_engine",
            payload={
                "project_id": project_id,
                "scene_number": scene_number,
                "model_name": model_name,
                "speaker": speaker,
                "error": error
            }
        )
        self._publish(event)
        
    def _publish(self, event: Event) -> None:
        try:
            self._event_bus.publish(event)
        except Exception as e:
            logger.debug("Failed to emit telemetry: %s", e)
