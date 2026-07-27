"""
JARVIS AIOS Task System

The smallest unit of work in JARVIS. 
Tasks describe work but NEVER execute it directly.
"""

from .enums import TaskStatus, TaskPriority
from .models import Task
from .exceptions import TaskError, InvalidTaskTransitionError, TaskNotFoundError, TaskValidationError
from .interfaces import TaskRepository
from .repository import InMemoryTaskRepository
from .queue import TaskQueue
from .validators import TaskValidator
from .manager import TaskManager
from .cancellation import CancellationToken

# Alias for backwards compatibility with Executor
TaskDefinition = Task

__all__ = [
    "TaskStatus",
    "TaskPriority",
    "Task",
    "TaskDefinition",
    "CancellationToken",
    "TaskError",
    "InvalidTaskTransitionError",
    "TaskNotFoundError",
    "TaskValidationError",
    "TaskRepository",
    "InMemoryTaskRepository",
    "TaskQueue",
    "TaskValidator",
    "TaskManager"
]
