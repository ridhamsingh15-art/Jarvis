class ExperienceError(Exception):
    """Base exception for the Experience Engine."""

class ExtractionError(ExperienceError):
    """Raised when experience cannot be extracted from a mission."""

class LearningError(ExperienceError):
    """Raised when lesson extraction or evaluation fails."""

class RetrievalError(ExperienceError):
    """Raised when relevant experience cannot be retrieved."""

class DuplicateExperienceError(ExperienceError):
    """Raised when an experience for the same mission already exists."""
