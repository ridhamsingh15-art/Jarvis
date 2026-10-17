class AutonomyError(Exception):
    """Base exception for the autonomy subsystem."""

class GoalCreationError(AutonomyError):
    """Raised when a goal cannot be created."""

class GoalExecutionError(AutonomyError):
    """Raised during errors in goal step execution."""

class PersistenceError(AutonomyError):
    """Raised when goal state cannot be saved or loaded."""

class SchedulingError(AutonomyError):
    """Raised during DAG scheduling issues, such as cyclic dependencies."""

class EvaluationError(AutonomyError):
    """Raised when goal evaluation fails."""
