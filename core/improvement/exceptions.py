class ImprovementError(Exception):
    """Base exception for the improvement subsystem."""

class AnalysisError(ImprovementError):
    """Raised when metric analysis fails."""

class OptimizationError(ImprovementError):
    """Raised during errors generating optimizations."""

class PolicyViolationError(ImprovementError):
    """Raised when an optimization violates a safety policy."""

class PersistenceError(ImprovementError):
    """Raised when improvement state cannot be saved or loaded."""
