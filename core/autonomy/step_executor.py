"""Goal-step execution contracts and safe defaults."""
from __future__ import annotations

from typing import Any

from .exceptions import GoalExecutionError
from .models import Goal, GoalStep


class IGoalStepExecutor:
    """Executes one goal step; implementations must perform real work."""

    async def execute(self, goal: Goal, step: GoalStep) -> Any:
        raise NotImplementedError


class UnconfiguredGoalStepExecutor(IGoalStepExecutor):
    """Fail closed instead of reporting simulated work as successful."""

    async def execute(self, goal: Goal, step: GoalStep) -> Any:
        raise GoalExecutionError(
            "No real goal-step executor is configured; refusing to simulate success. "
            f"Goal={goal.id.value}, step={step.id.value}."
        )
