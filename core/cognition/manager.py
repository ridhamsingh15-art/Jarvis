import logging
from typing import Any, Optional

from core.cognition.context import ShortTermContext
from core.cognition.conversation import ConversationEngine, ConversationResponse
from core.cognition.dialogue import DialogueState
from core.cognition.reflection import CognitiveReflection
from core.cognition.context_orchestrator import ContextOrchestrator
from core.executive.manager import ExecutiveBrain
from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Timestamp
from core.runtime.component import BaseComponent
from core.runtime.models import ComponentMetadata

logger = logging.getLogger(__name__)


class CognitiveManager(BaseComponent):
    """Facade for the Conversational Cognitive Core subsystem."""

    def __init__(
        self,
        conversation_engine: ConversationEngine,
        reflection: CognitiveReflection,
        context_orchestrator: ContextOrchestrator,
        executive_brain: Optional[ExecutiveBrain] = None,
        context: ShortTermContext = None,
        event_bus: EventBus = None,
    ):
        metadata = ComponentMetadata(
            id="cognitive_manager", name="Cognitive Manager", version="2.0.0"
        )
        super().__init__(metadata)
        self._engine = conversation_engine
        self._reflection = reflection
        self._context_orchestrator = context_orchestrator
        self._executive_brain = executive_brain
        self._context = context
        self._event_bus = event_bus
        self._dialogue_state = DialogueState()

    async def _do_start(self) -> None:
        logger.info("CognitiveManager started.")

    async def _do_stop(self) -> None:
        logger.info("CognitiveManager stopped.")

    def process_fast(self, message: str, intent: str = "chat") -> ConversationResponse:
        """Process a user message conversationally without engaging the ExecutiveBrain.

        Args:
            message: The user's message.
            intent: Routing intent ("chat", "tool", "memory") — used for deterministic
                    context provider selection. Defaults to "chat".
        """
        logger.info("CognitiveManager processing message via fast path (No ExecutiveBrain)")
        return self.process(message, plan=None, intent=intent)

    def process(self, message: str, plan: Optional[Any] = None, intent: str = "chat") -> ConversationResponse:
        """Process a user message conversationally.

        Args:
            message: The user's message.
            plan: Optional pre-computed ExecutionPlan (e.g., from an active mission).
            intent: Routing intent — forwarded to context orchestrator.
        """
        logger.info("CognitiveManager processing message conversationally")
        self._context.add_message("user", message)
        
        # If a pre-computed plan is supplied (e.g. from an active mission), check for clarification
        if plan is not None:
            if getattr(plan, "requires_clarification", False) and getattr(plan, "clarification_question", None):
                self._context.add_message("assistant", plan.clarification_question)
                return ConversationResponse(type="RESPONSE", message=plan.clarification_question)

        # Retrieve and inject context (deterministic by intent)
        context_package = self._context_orchestrator.build(message, self._context, plan=plan, intent=intent)

        # Process conversation
        response = self._engine.process(message, self._dialogue_state, context_package)
        self._context.add_message("assistant", response.message)

        # Publish cognitive event
        evt = Event(
            topic="cognition.conversation.processed",
            timestamp=Timestamp(),
            payload={
                "type": response.type,
                "message": response.message,
                "tool": response.tool
            },
            source=self.metadata.id,
        )
        try:
            self._event_bus.publish(evt)
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            logger.warning("Failed to publish conversation event: %s", e)

        return response

    def reflect(
        self,
        user_input: str,
        response_type: str,
        action: str,
        success: bool,
        execution_time: float,
    ) -> None:
        """Record the outcome of an interaction."""
        self._context.add_action(action)
        
        # After conversation, reflect and update memory
        try:
            last_msgs = self._context.get_context_summary()["messages"][-2:]
            if len(last_msgs) == 2 and last_msgs[0]["role"] == "user":
                self._reflection.reflect_on_conversation(
                    last_msgs[0]["content"],
                    last_msgs[1]["content"]
                )
        except Exception as e:
            logger.warning(f"Failed to run reflection post-conversation: {e}")

