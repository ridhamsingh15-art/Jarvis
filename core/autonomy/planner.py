import uuid

from core.models.primitives import Identifier

from .interfaces import IGoalPlanner
from .models import Goal, GoalPlan, GoalStep


class DefaultGoalPlanner(IGoalPlanner):
    """Provides mock generation of step graphs for evaluation."""

    def create_plan(self, goal: Goal) -> GoalPlan:
        # Mocks a 3-step linear graph for structural evaluations.
        s1 = Identifier(f"step_{uuid.uuid4().hex[:8]}")
        s2 = Identifier(f"step_{uuid.uuid4().hex[:8]}")
        s3 = Identifier(f"step_{uuid.uuid4().hex[:8]}")
        
        steps = [
            GoalStep(id=s1, description="Initialize constraints."),
            GoalStep(id=s2, description="Process bounds.", dependencies=[s1]),
            GoalStep(id=s3, description="Finalize payload.", dependencies=[s2])
        ]
        
        return GoalPlan(goal_id=goal.id, steps=steps)
