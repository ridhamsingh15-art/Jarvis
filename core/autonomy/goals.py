import threading

from .enums import GoalState
from .exceptions import GoalExecutionError
from .models import Goal


class GoalContext:
    """Manages transient thread-safe state for a single running goal."""

    def __init__(self, goal: Goal) -> None:
        self._lock = threading.RLock()
        self._goal = goal

    @property
    def goal(self) -> Goal:
        with self._lock:
            return self._goal

    def set_state(self, state: GoalState) -> None:
        with self._lock:
            terminal_states = (
                GoalState.COMPLETED,
                GoalState.FAILED,
                GoalState.CANCELLED,
            )
            if self._goal.state in terminal_states:
                if state != self._goal.state:
                    raise GoalExecutionError(
                        f"Cannot transition from terminal state {self._goal.state.value} to {state.value}."
                    )
                # Treat an idempotent write of the same terminal state as a no-op.
                return

            self._goal = Goal(
                id=self._goal.id,
                description=self._goal.description,
                state=state,
                priority=self._goal.priority,
                metadata=self._goal.metadata,
                timestamp=self._goal.timestamp
            )
