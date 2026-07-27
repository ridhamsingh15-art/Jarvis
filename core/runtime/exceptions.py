from core.errors import JarvisError

class RuntimeError(JarvisError):
    """Base exception for Runtime Kernel failures."""
    pass

class ComponentRegistrationError(RuntimeError):
    """Raised when component registration fails (e.g. duplicates)."""
    pass

class ComponentResolutionError(RuntimeError):
    """Raised when a requested component cannot be found in the registry."""
    pass
