"""
Exceptions for the AI Application Runtime.
"""

class ApplicationRuntimeError(Exception):
    """Base exception for application runtime errors."""

class AppInstallError(ApplicationRuntimeError):
    """Raised when an application fails to install."""

class AppUpdateError(ApplicationRuntimeError):
    """Raised when an application fails to update."""

class DependencyResolutionError(ApplicationRuntimeError):
    """Raised when an application's dependencies cannot be met."""

class InvalidManifestError(ApplicationRuntimeError):
    """Raised when an application's manifest is malformed."""

class AppLifecycleError(ApplicationRuntimeError):
    """Raised during invalid state transitions (e.g. suspending a stopped app)."""

class AppSandboxError(ApplicationRuntimeError):
    """Raised when an application attempts an operation outside its sandbox."""

class AppPermissionError(ApplicationRuntimeError):
    """Raised when an application lacks required permissions."""
