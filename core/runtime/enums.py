from enum import Enum

class RuntimeState(str, Enum):
    """Lifecycle state of the Runtime Kernel and its components."""
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
