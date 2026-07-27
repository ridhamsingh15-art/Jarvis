from core.errors import InternalError


class DependencyResolutionError(InternalError):
    """Raised when a dependency cannot be resolved."""
    pass


class CircularDependencyError(InternalError):
    """Raised when a cycle is detected in the dependency graph."""
    pass


class ContainerSealedError(InternalError):
    """Raised when an attempt is made to mutate a sealed container."""
    pass
