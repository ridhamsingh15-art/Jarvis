from core.errors import JarvisError


class WorkflowError(JarvisError):
    """Base exception for all Workflow System errors."""

class InvalidWorkflowTransitionError(WorkflowError):
    """Raised when an invalid state transition is attempted on a Workflow."""
    
class WorkflowNotFoundError(WorkflowError):
    """Raised when a requested Workflow cannot be found."""
    
class CyclicDependencyError(WorkflowError):
    """Raised when a cyclic dependency is detected in the Workflow graph."""
    
class WorkflowValidationError(WorkflowError):
    """Raised when a Workflow fails validation checks."""
