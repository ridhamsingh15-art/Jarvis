"""
Exceptions for the Project Bundle and Asset Manager.
"""

from core.exceptions import JarvisError


class ProjectManagerError(JarvisError):
    """Base exception for all Project Manager errors."""


class ProjectNotFoundError(ProjectManagerError):
    """Raised when a requested project ID cannot be found."""


class AssetNotFoundError(ProjectManagerError):
    """Raised when an asset is requested but does not exist in the bundle."""


class StorageError(ProjectManagerError):
    """Raised when disk I/O operations fail."""


class ProjectValidationError(ProjectManagerError):
    """Raised when the project bundle state is inconsistent or corrupted."""
