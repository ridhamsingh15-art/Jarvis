from core.errors import JarvisError

class ExecutorError(JarvisError):
    """Base exception for all Executor Engine failures."""
    pass

class ExecutionTimeoutError(ExecutorError):
    """Raised when a task exceeds its configured TimeoutPolicy."""
    pass
    
class ActionNotFoundError(ExecutorError):
    """Raised when the requested Task action string cannot be mapped."""
    pass

class WorkerError(ExecutorError):
    """Raised when a worker thread encounters a fatal internal error."""
    pass
