import builtins
from collections import defaultdict, deque

from .exceptions import SchedulingError
from .interfaces import IGoalScheduler
from .models import GoalPlan, GoalStep


class DAGGoalScheduler(IGoalScheduler):
    """Sorts step graph into execution waves based on directed dependencies."""

    def schedule(self, plan: GoalPlan) -> builtins.list[builtins.list[GoalStep]]:
        adj: dict[str, builtins.list[str]] = defaultdict(list)
        indegree: dict[str, int] = defaultdict(int)
        step_map: dict[str, GoalStep] = {}

        for step in plan.steps:
            step_map[step.id.value] = step
            indegree[step.id.value] = 0

        for step in plan.steps:
            for dep in step.dependencies:
                if dep.value not in step_map:
                    raise SchedulingError(f"Missing dependency {dep.value} for step {step.id.value}.")
                adj[dep.value].append(step.id.value)
                indegree[step.id.value] += 1

        waves: builtins.list[builtins.list[GoalStep]] = []
        q = deque([s for s in step_map if indegree[s] == 0])
        
        processed = 0

        while q:
            current_wave = []
            size = len(q)
            for _ in range(size):
                curr = q.popleft()
                current_wave.append(step_map[curr])
                processed += 1
                
                for neighbor in adj[curr]:
                    indegree[neighbor] -= 1
                    if indegree[neighbor] == 0:
                        q.append(neighbor)
                        
            waves.append(current_wave)

        if processed != len(plan.steps):
            raise SchedulingError("Cyclic dependency detected in goal plan.")

        return waves
