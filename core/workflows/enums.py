from enum import Enum

class WorkflowStatus(str, Enum):
    """Lifecycle states of a Workflow."""
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class WorkflowPriority(str, Enum):
    """Execution priority of a Workflow."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
