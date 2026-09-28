import datetime
import json
import logging

from core.cognition.enums import IntentType
from core.cognition.models import ExperienceRecord
from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Timestamp
from core.llm import LLMClient
from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

class CognitiveReflection:
    """Handles experience tracking and publishes them as events."""
    
    def __init__(self, event_bus: EventBus, llm_client: LLMClient, memory_manager: MemoryManager):
        self._event_bus = event_bus
        self._llm = llm_client
        self._memory_manager = memory_manager

    def reflect_on_conversation(self, user_input: str, assistant_response: str) -> None:
        """Analyzes the conversation to determine if anything should be remembered."""
        # Fast filter: skip reflection if input is trivial conversation or tool command
        cleaned = user_input.lower().strip()
        personal_markers = ("my ", "i am ", "i'm ", "remember", "prefer", "favorite", "favourite", "call me", "name is")
        if not any(marker in cleaned for marker in personal_markers):
            return

        prompt = f"""
Analyze the recent interaction to determine if any new, persistent user facts, preferences, or project details were shared.
Do not store temporary conversational noise.
If the user says "My name is X", you should store "user_name": "X".
If the user says "My favourite IDE is VS Code", you should store "favourite_ide": "VS Code".

User: {user_input}
Assistant: {assistant_response}

Return a JSON object:
{{
  "should_remember": true/false,
  "facts_to_store": {{"key": "value"}}
}}
"""
        try:
            resp = self._llm.generate("You are a JSON-only reflection engine.", prompt)
            text = resp.text if hasattr(resp, "text") else str(resp)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
                
            data = json.loads(text.strip())
            
            if data.get("should_remember") and data.get("facts_to_store"):
                for key, value in data["facts_to_store"].items():
                    self._memory_manager.remember_fact(key, str(value))
                    logger.info(f"Remembered fact: {key} = {value}")
                    
        except Exception as e:
            logger.warning(f"Reflection failed: {e}")


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
