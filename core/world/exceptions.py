class WorldModelError(Exception):
    """Base exception for the World Model subsystem."""

class WorkspaceNotFoundError(WorldModelError):
    """Raised when a workspace cannot be found by ID or path."""

class WorkspaceAlreadyRegisteredError(WorldModelError):
    """Raised when registering a workspace whose path is already tracked."""

class SnapshotError(WorldModelError):
    """Raised when a world snapshot cannot be generated."""

class ObserverError(WorldModelError):
    """Raised when an observer fails to collect state."""
