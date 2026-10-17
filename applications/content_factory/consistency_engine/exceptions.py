"""
Exceptions for the Character & Asset Consistency Engine.
"""

from core.errors import JarvisError


class ConsistencyEngineError(JarvisError):
    """Base exception for the consistency engine."""
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ConsistencyValidationError(ConsistencyEngineError):
    """Raised when a profile fails validation."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_code = "CONSISTENCY_VALIDATION_ERROR"


class ProfileNotFoundError(ConsistencyEngineError):
    """Raised when a requested profile is not found in the registry."""
    def __init__(self, profile_type: str, profile_id: str) -> None:
        super().__init__(f"{profile_type} profile '{profile_id}' not found.")
        self.error_code = "PROFILE_NOT_FOUND"
