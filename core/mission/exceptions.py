from core.errors import JarvisError


class MissionError(JarvisError):
    """Base exception for all Mission System errors."""

class InvalidMissionTransitionError(MissionError):
    """Raised when an invalid state transition is attempted on a Mission."""
    
class MissionNotFoundError(MissionError):
    """Raised when a requested Mission cannot be found."""
