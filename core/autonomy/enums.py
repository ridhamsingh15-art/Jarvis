from enum import StrEnum


class GoalState(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class GoalPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class StepState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"

class RetryStrategy(StrEnum):
    LINEAR = "LINEAR"
    EXPONENTIAL_BACKOFF = "EXPONENTIAL_BACKOFF"
    NONE = "NONE"
