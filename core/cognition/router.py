from core.cognition.confidence import evaluate_confidence
from core.cognition.enums import DecisionType, IntentType
from core.cognition.models import CognitiveDecision, IntentResult


class CognitiveRouter:
    """Routes an IntentResult to a concrete CognitiveDecision."""

    def route(self, result: IntentResult) -> CognitiveDecision:
        """Determine the next step for a given intent."""
        base_decision = self._map_intent_to_decision(result.intent)
        final_decision_type = evaluate_confidence(result, base_decision)
        
        target = self._map_decision_to_target(final_decision_type)
        
        return CognitiveDecision(
            decision_type=final_decision_type,
            intent_result=result,
            target_component=target
        )

    def _map_intent_to_decision(self, intent: IntentType) -> DecisionType:
        if intent in (IntentType.CHAT, IntentType.QUESTION):
            return DecisionType.DIRECT_RESPONSE
        elif intent == IntentType.SIMPLE_ACTION:
            return DecisionType.EXECUTE_ACTION
        elif intent == IntentType.COMPLEX_GOAL or intent == IntentType.LEARN:
            return DecisionType.CREATE_PLAN
        return DecisionType.ASK_CLARIFICATION

    def _map_decision_to_target(self, decision: DecisionType) -> str:
        if decision == DecisionType.EXECUTE_ACTION:
            return "Executor"
        elif decision == DecisionType.CREATE_PLAN:
            return "Planner"
        elif decision in (DecisionType.DIRECT_RESPONSE, DecisionType.ASK_CLARIFICATION):
            return "System"
        return "Unknown"
