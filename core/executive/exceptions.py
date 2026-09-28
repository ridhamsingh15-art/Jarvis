class ExecutiveBrainError(Exception):
    """Base exception for Executive Brain errors."""
    pass

class ReasoningFailedError(ExecutiveBrainError):
    """Raised when the LLM fails to reason about the user's input."""
    pass
