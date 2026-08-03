import logging

from core.cognition.classifier import IntentClassifier
from core.cognition.context import ShortTermContext
from core.cognition.enums import IntentType
from core.cognition.models import CognitiveDecision, IntentResult
from core.cognition.reflection import CognitiveReflection
from core.cognition.router import CognitiveRouter
from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Timestamp
from core.runtime.component import BaseComponent
from core.runtime.models import ComponentMetadata

logger = logging.getLogger(__name__)

class CognitiveManager(BaseComponent):
    """Facade for the Cognitive Core subsystem."""
    
    def __init__(
        self, 
        classifier: IntentClassifier, 
        router: CognitiveRouter, 
        reflection: CognitiveReflection, 
        context: ShortTermContext, 
        event_bus: EventBus
    ):
        metadata = ComponentMetadata(id="cognitive_manager", name="Cognitive Manager", version="1.0.0")
        super().__init__(metadata)
        self._classifier = classifier
        self._router = router
        self._reflection = reflection
        self._context = context
        self._event_bus = event_bus

    async def _do_start(self) -> None:
        logger.info("CognitiveManager started.")

    async def _do_stop(self) -> None:
        logger.info("CognitiveManager stopped.")

    def analyze(self, message: str) -> IntentResult:
        """Classify user input into an IntentResult."""
        logger.info("CognitiveManager analyzing message")
        self._context.add_message("user", message)
        
        result = self._classifier.classify(message)
        
        # Publish intent detected event
        evt = Event(
            topic="cognition.intent.detected",
            timestamp=Timestamp(),
            payload=result.to_dict(),
            source=self.metadata.id
        )
        try:
            self._event_bus.publish(evt)
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            logger.warning("Failed to publish intent event: %s", e)
            
        self._context.add_intent(result.intent)
        return result

    def decide(self, intent: IntentResult) -> CognitiveDecision:
        """Map an IntentResult to a CognitiveDecision."""
        logger.info("CognitiveManager making decision for intent: %s (confidence: %.2f)", 
                    intent.intent.name, intent.confidence)
        
        decision = self._router.route(intent)
        
        # Publish decision created event
        evt = Event(
            topic="cognition.decision.created",
            timestamp=Timestamp(),
            payload=decision.to_dict(),
            source=self.metadata.id
        )
        try:
            self._event_bus.publish(evt)
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            logger.warning("Failed to publish decision event: %s", e)
            
        return decision

    def reflect(
        self,
        user_input: str,
        intent: IntentType,
        action: str,
        success: bool,
        execution_time: float
    ) -> None:
        """Record the outcome of an interaction."""
        self._reflection.record_experience(user_input, intent, action, success, execution_time)
        self._context.add_action(action)
