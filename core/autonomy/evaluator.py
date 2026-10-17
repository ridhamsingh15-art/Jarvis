from .enums import GoalState
from .interfaces import IGoalEvaluator
from .models import Goal, GoalEvaluation, GoalHistory


class DefaultGoalEvaluator(IGoalEvaluator):
    """Abstracts success boundaries post-execution."""

    def evaluate(self, goal: Goal, history: GoalHistory) -> GoalEvaluation:
        # Trivial deterministic evaluation mapping completion states
        success = goal.state == GoalState.COMPLETED
        metrics = {
            "history_len": len(history.logs),
            "final_state": goal.state.value
        }
        return GoalEvaluation(
            goal_id=goal.id,
            success=success,
            metrics=metrics
        )
