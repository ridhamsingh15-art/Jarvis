from core.errors import JarvisError

class MissionError(JarvisError):
    """Base exception for all Mission System errors."""
    pass

class InvalidMissionTransitionError(MissionError):
    """Raised when an invalid state transition is attempted on a Mission."""
    pass
    
class MissionNotFoundError(MissionError):
    """Raised when a requested Mission cannot be found."""
    pass
