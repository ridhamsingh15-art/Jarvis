class SkillError(Exception):
    """Base exception for all skill-related errors."""

class SkillNotFoundError(SkillError):
    """Raised when a requested skill cannot be found."""

class DuplicateSkillError(SkillError):
    """Raised when attempting to register a skill that already exists."""

class SkillValidationError(SkillError):
    """Raised when a skill fails validation checks."""

class SkillExecutionError(SkillError):
    """Raised when a skill fails during execution."""
