import builtins
import copy
import threading

from core.models.primitives import Identifier

from .interfaces import IGoalPersistence
from .models import Goal, GoalPlan


class InMemoryGoalPersistence(IGoalPersistence):
    """Tracks thread-safe deep-copy states acting as a local checkpoint layer."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._goals: dict[str, Goal] = {}
        self._plans: dict[str, GoalPlan] = {}

    def save_goal(self, goal: Goal) -> None:
        with self._lock:
            self._goals[goal.id.value] = copy.deepcopy(goal)

    def get_goal(self, goal_id: Identifier) -> Goal | None:
        with self._lock:
            val = self._goals.get(goal_id.value)
            return copy.deepcopy(val) if val else None

    def save_plan(self, plan: GoalPlan) -> None:
        with self._lock:
            self._plans[plan.goal_id.value] = copy.deepcopy(plan)

    def get_plan(self, goal_id: Identifier) -> GoalPlan | None:
        with self._lock:
            val = self._plans.get(goal_id.value)
            return copy.deepcopy(val) if val else None

    def list_goals(self) -> builtins.list[Goal]:
        with self._lock:
            return [copy.deepcopy(g) for g in self._goals.values()]
