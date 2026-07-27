from core.errors import JarvisError

class SchedulerError(JarvisError):
    """Base exception for all Scheduler failures."""
    pass

class InvalidScheduleError(SchedulerError):
    """Raised when a schedule definition is invalid."""
    pass
