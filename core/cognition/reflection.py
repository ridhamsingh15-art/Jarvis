import datetime
import logging

from core.cognition.enums import IntentType
from core.cognition.models import ExperienceRecord
from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Timestamp

logger = logging.getLogger(__name__)

class CognitiveReflection:
    """Handles experience tracking and publishes them as events."""
    
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus

    def record_experience(
        self,
        user_input: str,
        intent: IntentType,
        action: str,
        success: bool,
        execution_time: float
    ) -> ExperienceRecord:
        """Create an ExperienceRecord and publish it to the EventBus."""
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        record = ExperienceRecord(
            user_input=user_input,
            intent=intent,
            action=action,
            success=success,
            execution_time=execution_time,
            timestamp=timestamp_str
        )
        
        # Ensure timestamp for Event is created correctly
        evt_timestamp = Timestamp()
        
        event = Event(
            topic="cognition.experience.created",
            timestamp=evt_timestamp,
            payload=record.to_dict(),
            source="CognitiveManager"
        )
        
        try:
            self._event_bus.publish(event)
            logger.debug("Published cognition.experience.created event.")
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            logger.warning("Failed to publish experience event: %s", e)
            
        return record
