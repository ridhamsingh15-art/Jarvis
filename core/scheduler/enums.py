from enum import Enum


class ScheduleStatus(str, Enum):
    """Canonical lifecycle state of a scheduled job."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    
class JobType(str, Enum):
    """Type of payload the scheduler is managing."""
    TASK = "TASK"
    WORKFLOW = "WORKFLOW"
