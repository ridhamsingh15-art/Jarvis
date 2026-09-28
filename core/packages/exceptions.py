class PackageError(Exception):
    """Base exception for the package manager subsystem."""

class DownloadError(PackageError):
    """Raised when a package fails to download."""

class DependencyError(PackageError):
    """Raised when dependencies cannot be resolved or have cycles."""

class SignatureError(PackageError):
    """Raised when a package's signature is invalid or checksum fails."""

class InstallError(PackageError):
    """Raised when a package fails to install."""

class RollbackError(PackageError):
    """Raised when a package fails to rollback to a previous state."""
