class CreatorError(Exception):
    """Base exception for the Creator Agent."""
    pass

class ObjectiveParsingError(CreatorError):
    """Raised when the Creator fails to parse the user's objective into actionable steps."""
    pass

class WorkflowResolutionError(CreatorError):
    """Raised when the Dependency Graph cannot be resolved into a valid execution workflow (e.g. cycles)."""
    pass

class ProductionExecutionError(CreatorError):
    """Raised when an unrecoverable failure occurs during the production pipeline execution."""
    pass

class ProjectBundleError(CreatorError):
    """Raised when the Creator fails to initialize or mutate the shared Project Bundle."""
    pass
