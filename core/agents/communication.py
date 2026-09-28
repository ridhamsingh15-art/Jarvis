import builtins
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Identifier, Timestamp

logger = logging.getLogger(__name__)

class MessageType(StrEnum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    FEEDBACK = "FEEDBACK"
    REVISION = "REVISION"

@dataclass(frozen=True, slots=True)
class AgentMessage:
    """Immutable typed message between agents/coordinator."""
    id: Identifier = field(default_factory=Identifier)
    sender_id: Identifier = field(default_factory=Identifier)
    receiver_id: Identifier = field(default_factory=Identifier)
    message_type: MessageType = MessageType.REQUEST
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: Timestamp = field(default_factory=Timestamp)
    reply_to_id: Identifier | None = None

class MessageBus:
    """
    Centralized communication adapter for agents. 
    Prevents direct agent-to-agent coupling by using the core EventBus.
    """
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus

    def send(self, message: AgentMessage) -> None:
        """Sends a structured message via the event bus."""
        event_topic = f"agent.message.{message.message_type.value.lower()}"
        
        event_payload = {
            "message_id": message.id.value,
            "sender_id": message.sender_id.value,
            "receiver_id": message.receiver_id.value,
            "payload": message.payload,
        }
        
        if message.reply_to_id:
            event_payload["reply_to_id"] = message.reply_to_id.value
            
        event = Event(
            topic=event_topic,
            payload=event_payload,
            source="core.agents.communication"
        )
        
        self._event_bus.publish(event)
        logger.debug(f"Message sent: {message.sender_id.value} -> {message.receiver_id.value} [{message.message_type.value}]")
