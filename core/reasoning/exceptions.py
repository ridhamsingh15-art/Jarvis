class ReasoningError(Exception):
    pass

class SimulationError(Exception):
    pass

class MaxIterationsExceededError(ReasoningError):
    """Raised when the Reasoning Loop iterates too many times without finalizing."""
    pass
