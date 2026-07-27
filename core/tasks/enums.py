from enum import Enum

class TaskStatus(str, Enum):
    """Lifecycle states of a Task."""
    CREATED = "CREATED"
    READY = "READY"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"

class TaskPriority(str, Enum):
    """Execution priority of a Task."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
