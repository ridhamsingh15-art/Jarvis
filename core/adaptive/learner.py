from .enums import LearningDecision, PatternType
from .interfaces import Learner
from .models import LearningPattern, LearningRecommendation
from .policy import LearningPolicy


class RuleBasedLearner(Learner):
    """
    Applies deterministic rules and policies to generate learning recommendations.
    """

    def __init__(self, policy: LearningPolicy) -> None:
        self._policy = policy

    def learn(self, patterns: list[LearningPattern]) -> list[LearningRecommendation]:
        recommendations: list[LearningRecommendation] = []

        for pattern in patterns:
            decision, reason = self._evaluate_pattern(pattern)
            
            # Extract target skill ID if applicable (e.g. from SKILL pattern)
            target_skill = None
            if pattern.pattern_type == PatternType.SKILL:
                # In this simple logic, if it's a SKILL pattern, the source experiences 
                # all map to the same skill. However, we didn't store the skill_id directly 
                # in the pattern except maybe in metadata. Let's assume metadata could hold it,
                # or we just let Optimizer handle it by looking at source_experiences.
                pass
                
            recommendations.append(LearningRecommendation(
                decision=decision,
                reason=reason,
                confidence=pattern.confidence,
                target_skill=target_skill
            ))

        return recommendations

    def _evaluate_pattern(self, pattern: LearningPattern) -> tuple[LearningDecision, str]:
        if pattern.occurrences < self._policy.minimum_repetitions:
            return LearningDecision.IGNORE, f"Occurrences ({pattern.occurrences}) below threshold."

        if pattern.pattern_type == PatternType.WORKFLOW:
            if pattern.confidence >= self._policy.minimum_success_rate:
                return LearningDecision.CREATE_SKILL, "Consistently successful workflow detected."
            else:
                return LearningDecision.IGNORE, "Workflow success rate too low to automate."
                
        elif pattern.pattern_type == PatternType.SKILL:
            if pattern.confidence < self._policy.minimum_success_rate:
                # Skill is failing often
                return LearningDecision.OPTIMIZE_SKILL, "Skill failing frequently. Optimization recommended."
            else:
                return LearningDecision.IGNORE, "Skill performing adequately."
                
        elif pattern.pattern_type == PatternType.TASK_SEQUENCE:
            if pattern.confidence >= self._policy.minimum_success_rate:
                return LearningDecision.CREATE_SKILL, "Consistently successful task sequence."
            else:
                return LearningDecision.IGNORE, "Task sequence success rate too low."

        return LearningDecision.IGNORE, "No actionable rule matched."
