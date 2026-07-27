from enum import Enum

class WorkerStatus(str, Enum):
    """Canonical lifecycle state of a Worker."""
    IDLE = "IDLE"
    BUSY = "BUSY"
    STOPPED = "STOPPED"
