from typing import ClassVar

from .enums import TaskStatus
from .exceptions import InvalidTaskTransitionError, TaskValidationError


class TaskValidator:
    """Validates task definitions, configurations, and state transitions."""
    
    VALID_TRANSITIONS: ClassVar[dict[TaskStatus, set[TaskStatus]]] = {
        TaskStatus.CREATED: {TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.QUEUED},
        TaskStatus.BLOCKED: {TaskStatus.READY, TaskStatus.CANCELLED},
        TaskStatus.READY: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
        TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
        TaskStatus.RUNNING: {TaskStatus.PAUSED, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.PAUSED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
        TaskStatus.COMPLETED: set(),
        TaskStatus.FAILED: {TaskStatus.READY}, # Allowing retry
        TaskStatus.CANCELLED: set()
    }
    
    @classmethod
    def validate_transition(cls, current_status: TaskStatus, new_status: TaskStatus) -> None:
        """Validates if a state transition is legal."""
        if new_status not in cls.VALID_TRANSITIONS[current_status]:
            raise InvalidTaskTransitionError(
                f"Cannot transition Task from {current_status.value} to {new_status.value}"
            )
            
    @classmethod
    def validate_task_configuration(cls, timeout_seconds: int | None, retry_count: int, max_retries: int) -> None:
        """Validates retry and timeout bounds."""
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise TaskValidationError("timeout_seconds must be strictly positive.")
            
        if max_retries < 0:
            raise TaskValidationError("max_retries cannot be negative.")
            
        if retry_count < 0:
            raise TaskValidationError("retry_count cannot be negative.")
            
        if retry_count > max_retries:
            raise TaskValidationError("retry_count cannot exceed max_retries.")
