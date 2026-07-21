"""
Task dataclass representing a single unit of work.

A Task flows through the pipeline carrying its tool, action,
arguments, execution status, result, and any error. State
transitions are guarded to prevent illegal flows.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.exceptions import InvalidStateError


class TaskStatus(Enum):
    """Lifecycle states of a Task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Valid state transitions: current_state -> set of allowed next states
_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
}


@dataclass
class Task:
    """One executable unit of work in the Jarvis pipeline.

    Attributes:
        tool: Name of the tool to invoke (e.g. 'windows').
        action: Action to perform on the tool (e.g. 'open_app').
        args: Arguments for the action.
        status: Current lifecycle state.
        result: Output from successful execution.
        error: Error message from failed execution.
    """

    tool: str
    action: str
    args: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""

    def _transition(self, target: TaskStatus) -> None:
        """Transition to a new state, enforcing valid transitions.

        Args:
            target: The desired next state.

        Raises:
            InvalidStateError: If the transition is not allowed.
        """
        allowed = _TRANSITIONS.get(self.status, set())

        if target not in allowed:
            raise InvalidStateError(
                f"Cannot transition from {self.status.value} "
                f"to {target.value}"
            )

        self.status = target

    def start(self) -> None:
        """Mark this task as running. Only valid from PENDING."""
        self._transition(TaskStatus.RUNNING)

    def complete(self, result: Any = None) -> None:
        """Mark this task as completed. Only valid from RUNNING.

        Args:
            result: The execution result to store.
        """
        self._transition(TaskStatus.COMPLETED)
        self.result = result

    def fail(self, error: str) -> None:
        """Mark this task as failed. Only valid from RUNNING.

        Args:
            error: Human-readable error description.
        """
        self._transition(TaskStatus.FAILED)
        self.error = error

    @property
    def is_terminal(self) -> bool:
        """Whether this task has reached a final state."""
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}