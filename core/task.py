"""
Task dataclass representing a single unit of work.

A Task flows through the pipeline carrying its tool, action,
arguments, execution status, result, and any error. State
transitions are guarded to prevent illegal flows, with an explicit
controlled retry lifecycle:
    PENDING -> RUNNING -> FAILED -> RETRYING -> RUNNING -> COMPLETED
"""

from __future__ import annotations

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
    RETRYING = "retrying"


# Valid state transitions: current_state -> set of allowed next states
_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.FAILED: {TaskStatus.RETRYING},
    TaskStatus.RETRYING: {TaskStatus.RUNNING, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
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
        retry_count: Number of times this task has been retried.
        max_retries: Maximum permitted retries for this task (default 3).
        failure_history: Preserved error log from prior failed attempts.
    """

    tool: str
    action: str
    args: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""
    retry_count: int = 0
    max_retries: int = 3
    failure_history: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Normalize status to TaskStatus enum at construction boundary."""
        if isinstance(self.status, str):
            status_str: str = self.status
            try:
                self.status = TaskStatus(status_str)
            except ValueError:
                # Try matching by name (e.g. "COMPLETED" -> TaskStatus.COMPLETED)
                try:
                    self.status = TaskStatus[status_str.upper()]
                except KeyError:
                    self.status = TaskStatus.PENDING

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
        """Mark this task as running. Only valid from PENDING or RETRYING."""
        self._transition(TaskStatus.RUNNING)

    def complete(self, result: Any = None) -> None:
        """Mark this task as completed. Only valid from RUNNING.

        Args:
            result: The execution result to store.
        """
        self._transition(TaskStatus.COMPLETED)
        self.result = result

    def fail(self, error: str) -> None:
        """Mark this task as failed. Only valid from RUNNING or RETRYING.

        Args:
            error: Human-readable error description.
        """
        self._transition(TaskStatus.FAILED)
        self.error = error

    def retry(self) -> None:
        """Controlled transition from FAILED to RETRYING.

        Preserves active failure into failure_history, increments retry_count,
        clears active error/result, and checks retry limits.

        Raises:
            InvalidStateError: If not in FAILED state, or if retry limit reached.
        """
        if self.status != TaskStatus.FAILED:
            raise InvalidStateError(
                f"Cannot retry task in {self.status.value} state. Only failed tasks can be retried."
            )
        if self.retry_count >= self.max_retries:
            raise InvalidStateError(
                f"Cannot retry task: retry limit reached ({self.retry_count}/{self.max_retries})"
            )

        if self.error:
            self.failure_history.append(self.error)
        self.error = ""
        self.result = None
        self.retry_count += 1
        self._transition(TaskStatus.RETRYING)

    @property
    def is_terminal(self) -> bool:
        """Whether this task has reached a final state."""
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}