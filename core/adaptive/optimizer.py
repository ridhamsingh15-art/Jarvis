from .enums import LearningDecision
from .interfaces import Optimizer
from .models import LearningRecommendation, OptimizationPlan


class PlanOptimizer(Optimizer):
    """
    Translates learning recommendations into actionable optimization plans.
    """

    def optimize(self, recommendations: list[LearningRecommendation]) -> OptimizationPlan:
        plan = OptimizationPlan()

        for rec in recommendations:
            if rec.decision == LearningDecision.IGNORE:
                continue
                
            if rec.decision == LearningDecision.CREATE_SKILL:
                plan.planner_hints.append(
                    f"Consider creating a new skill for highly successful pattern. Reason: {rec.reason}"
                )
                
            elif rec.decision == LearningDecision.OPTIMIZE_SKILL:
                if rec.target_skill:
                    # Decrease confidence score to discourage usage until fixed
                    plan.skill_confidence_adjustments[rec.target_skill.value] = -0.2
                else:
                    plan.planner_hints.append(
                        f"Optimize skill due to failures. Reason: {rec.reason}"
                    )
                    
            elif rec.decision == LearningDecision.STORE:
                plan.planner_hints.append("Stored pattern for future baseline.")

        return plan
