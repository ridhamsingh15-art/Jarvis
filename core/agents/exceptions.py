class AgentSystemError(Exception):
    """Base exception for the agent subsystem."""

class TaskDelegationError(AgentSystemError):
    """Raised when task delegation fails."""

class VotingError(AgentSystemError):
    """Raised when consensus voting encounters an error."""

class CollaborationError(AgentSystemError):
    """Raised during collaboration session issues."""

class RegistryError(AgentSystemError):
    """Raised during agent registry lookup or registration errors."""

class ExecutionTimeoutError(AgentSystemError):
    """Raised when an agent task times out."""
