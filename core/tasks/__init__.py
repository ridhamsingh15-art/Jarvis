"""
JARVIS AIOS Task System

The smallest unit of work in JARVIS. 
Tasks describe work but NEVER execute it directly.
"""

from .cancellation import CancellationToken
from .enums import TaskPriority, TaskStatus
from .exceptions import (
    InvalidTaskTransitionError,
    TaskError,
    TaskNotFoundError,
    TaskValidationError,
)
from .interfaces import TaskRepository
from .manager import TaskManager
from .models import Task
from .queue import TaskQueue
from .repository import InMemoryTaskRepository
from .validators import TaskValidator

# Alias for backwards compatibility with Executor
TaskDefinition = Task

__all__ = [
    "CancellationToken",
    "InMemoryTaskRepository",
    "InvalidTaskTransitionError",
    "Task",
    "TaskDefinition",
    "TaskError",
    "TaskManager",
    "TaskNotFoundError",
    "TaskPriority",
    "TaskQueue",
    "TaskRepository",
    "TaskStatus",
    "TaskValidationError",
    "TaskValidator"
]
