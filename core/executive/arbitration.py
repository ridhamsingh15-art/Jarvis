from .decision import ExecutiveDecision


class ConflictArbitrator:
    def resolve(self, recommendations: dict[str, ExecutiveDecision]) -> ExecutiveDecision:
        # Hierarchy: ESCALATE > CANCEL > PAUSE > CLARIFY > DEFER > DELEGATE > RESUME > PROCEED
        hierarchy = {
            ExecutiveDecision.ESCALATE: 8,
            ExecutiveDecision.CANCEL: 7,
            ExecutiveDecision.PAUSE: 6,
            ExecutiveDecision.CLARIFY: 5,
            ExecutiveDecision.DEFER: 4,
            ExecutiveDecision.DELEGATE: 3,
            ExecutiveDecision.RESUME: 2,
            ExecutiveDecision.PROCEED: 1
        }
        
        if not recommendations:
            return ExecutiveDecision.PROCEED
            
        best = ExecutiveDecision.PROCEED
        best_score = 0
        
        for decision in recommendations.values():
            score = hierarchy.get(decision, 0)
            if score > best_score:
                best_score = score
                best = decision
                
        return best
