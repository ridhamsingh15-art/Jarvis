"""
Telemetry for the Character & Asset Consistency Engine.
"""

import logging
from datetime import datetime, timezone
from typing import List

from core.events.bus import EventBus, Event

logger = logging.getLogger(__name__)


class ConsistencyTelemetry:
    """Publishes telemetry events for the consistency engine."""
    
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def emit_enrichment_completed(
        self,
        project_id: str,
        scene_number: int,
        matched_chars: List[str],
        matched_envs: List[str],
        matched_objs: List[str]
    ) -> None:
        """Emits an event when a scene prompt is successfully enriched."""
        event = Event(
            topic="content_factory.consistency.enrichment_completed",
            source="consistency_engine",
            payload={
                "project_id": project_id,
                "scene_number": scene_number,
                "matched_characters": matched_chars,
                "matched_environments": matched_envs,
                "matched_objects": matched_objs,
                "total_matches": len(matched_chars) + len(matched_envs) + len(matched_objs),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        try:
            self._event_bus.publish(event)
        except Exception as e:
            logger.debug("Failed to emit enrichment_completed telemetry: %s", e)

    def emit_profile_registered(self, project_id: str, profile_type: str, profile_name: str) -> None:
        """Emits an event when a new profile is registered for a project."""
        event = Event(
            topic="content_factory.consistency.profile_registered",
            source="consistency_engine",
            payload={
                "project_id": project_id,
                "profile_type": profile_type,
                "profile_name": profile_name,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        try:
            self._event_bus.publish(event)
        except Exception as e:
            logger.debug("Failed to emit profile_registered telemetry: %s", e)
