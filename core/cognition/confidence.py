from core.cognition.enums import DecisionType
from core.cognition.models import IntentResult


def evaluate_confidence(result: IntentResult, base_decision: DecisionType) -> DecisionType:
    """Evaluate confidence and modify decision type if necessary."""
    if result.confidence >= 0.85:
        # High confidence: proceed with the intended decision
        return base_decision
    elif result.confidence >= 0.50:
        # Medium confidence: ask for confirmation
        # We can map this to ASK_CLARIFICATION for now, or if there was an ASK_CONFIRMATION we would use it.
        # Requirements state < 0.50 is clarify, 0.50 - 0.85 is confirm.
        # But DecisionType only has ASK_CLARIFICATION. Let's use ASK_CLARIFICATION for both or add CONFIRMATION if needed.
        # The enums requirement: DecisionType = DIRECT_RESPONSE, EXECUTE_ACTION, CREATE_PLAN, ASK_CLARIFICATION.
        # I'll use ASK_CLARIFICATION for anything under 0.85 since there is no ASK_CONFIRMATION in the required enums.
        return DecisionType.ASK_CLARIFICATION
    else:
        # Low confidence: ask for clarification
        return DecisionType.ASK_CLARIFICATION
