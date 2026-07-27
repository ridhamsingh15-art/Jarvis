from enum import Enum

class MemoryType(str, Enum):
    """Classification of memory domains."""
    WORKING = "WORKING"
    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
