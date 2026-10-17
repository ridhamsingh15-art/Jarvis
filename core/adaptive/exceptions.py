class AdaptiveLearningError(Exception):
    """Base exception for the adaptive learning subsystem."""

class ExperienceNotFoundError(AdaptiveLearningError):
    """Raised when a specified experience is not found."""

class PatternDetectionError(AdaptiveLearningError):
    """Raised when pattern detection fails."""

class LearningPolicyError(AdaptiveLearningError):
    """Raised when a learning policy is invalid or violated."""

class OptimizationError(AdaptiveLearningError):
    """Raised when an optimization failure occurs."""
