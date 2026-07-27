from core.errors import JarvisError

class WorkflowError(JarvisError):
    """Base exception for all Workflow System errors."""
    pass

class InvalidWorkflowTransitionError(WorkflowError):
    """Raised when an invalid state transition is attempted on a Workflow."""
    pass
    
class WorkflowNotFoundError(WorkflowError):
    """Raised when a requested Workflow cannot be found."""
    pass
    
class CyclicDependencyError(WorkflowError):
    """Raised when a cyclic dependency is detected in the Workflow graph."""
    pass
    
class WorkflowValidationError(WorkflowError):
    """Raised when a Workflow fails validation checks."""
    pass
