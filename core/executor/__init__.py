"""
JARVIS AIOS Executor Engine

The canonical execution engine for executing Ready tasks via bounded Worker Pools.
"""

from .enums import WorkerStatus
from .exceptions import ExecutorError, ExecutionTimeoutError, ActionNotFoundError, WorkerError
from .models import ExecutionContext
from .action_registry import ActionRegistry
from .results import ExecutionResultBuilder
from .worker import WorkerThread
from .pool import WorkerPool
from .timeouts import TimeoutEnforcer
from .executor import ExecutionEngine, ExecutionEngine as Executor
from .dispatcher import TaskDispatcher
from .manager import ExecutorManager

__all__ = [
    "WorkerStatus",
    "ExecutorError", "ExecutionTimeoutError", "ActionNotFoundError", "WorkerError",
    "ExecutionContext",
    "ActionRegistry",
    "ExecutionResultBuilder",
    "WorkerThread",
    "WorkerPool",
    "TimeoutEnforcer",
    "ExecutionEngine", "Executor",
    "TaskDispatcher",
    "ExecutorManager"
]
