from .decision import DecisionContext, ExecutiveDecision


class ReflectionEngine:
    def __init__(self) -> None:
        self.history: list[dict] = []

    def reflect(self, context: DecisionContext, decision: ExecutiveDecision, outcome: str) -> None:
        self.history.append({
            "context": context.to_dict(),
            "decision": decision.value,
            "outcome": outcome
        })
