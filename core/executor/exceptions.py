from core.errors import JarvisError


class ExecutorError(JarvisError):
    """Base exception for all Executor Engine failures."""

class ExecutionTimeoutError(ExecutorError):
    """Raised when a task exceeds its configured TimeoutPolicy."""
    
class ActionNotFoundError(ExecutorError):
    """Raised when the requested Task action string cannot be mapped."""

class WorkerError(ExecutorError):
    """Raised when a worker thread encounters a fatal internal error."""
