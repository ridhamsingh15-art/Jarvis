import builtins
from abc import ABC, abstractmethod

from core.models.primitives import Identifier

from .models import Goal, GoalEvaluation, GoalHistory, GoalPlan, GoalStep


class IGoalPlanner(ABC):
    """Abstract interface for decomposing goals into plans."""

    @abstractmethod
    def create_plan(self, goal: Goal) -> GoalPlan:
        pass


class IGoalScheduler(ABC):
    """Abstract interface for managing execution of step graphs."""

    @abstractmethod
    def schedule(self, plan: GoalPlan) -> builtins.list[builtins.list[GoalStep]]:
        pass


class IGoalEvaluator(ABC):
    """Abstract interface for checking if a goal succeeded."""

    @abstractmethod
    def evaluate(self, goal: Goal, history: GoalHistory) -> GoalEvaluation:
        pass


class IRetryPolicy(ABC):
    """Abstract interface for computing backoff intervals."""

    @abstractmethod
    def get_delay(self, current_retry: int) -> float:
        pass


class IGoalPersistence(ABC):
    """Abstract interface for checkpointing goal states."""

    @abstractmethod
    def save_goal(self, goal: Goal) -> None:
        pass

    @abstractmethod
    def get_goal(self, goal_id: Identifier) -> Goal | None:
        pass

    @abstractmethod
    def save_plan(self, plan: GoalPlan) -> None:
        pass

    @abstractmethod
    def get_plan(self, goal_id: Identifier) -> GoalPlan | None:
        pass
        
    @abstractmethod
    def list_goals(self) -> builtins.list[Goal]:
        pass
