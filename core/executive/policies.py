from .decision import DecisionContext, ExecutiveDecision


class ExecutivePolicies:
    def evaluate(self, context: DecisionContext) -> ExecutiveDecision | None:
        if context.risk > 0.9:
            return ExecutiveDecision.ESCALATE
        if context.confidence < 0.2:
            return ExecutiveDecision.CLARIFY
        if context.urgency > 0.8:
            return ExecutiveDecision.PROCEED
        return None
