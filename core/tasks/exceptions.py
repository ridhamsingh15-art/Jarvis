from core.errors import JarvisError

class TaskError(JarvisError):
    """Base exception for all Task System errors."""
    pass

class InvalidTaskTransitionError(TaskError):
    """Raised when an invalid state transition is attempted on a Task."""
    pass
    
class TaskNotFoundError(TaskError):
    """Raised when a requested Task cannot be found."""
    pass
    
class TaskValidationError(TaskError):
    """Raised when a Task fails validation checks (e.g. invalid retry or timeout values)."""
    pass
