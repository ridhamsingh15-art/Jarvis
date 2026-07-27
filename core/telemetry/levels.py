from enum import Enum, auto


class LogLevel(Enum):
    """
    Standardized log levels for the JARVIS AIOS telemetry system.
    """
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40
    FATAL = 50

    @classmethod
    def from_string(cls, level_str: str) -> "LogLevel":
        """
        Safely parse a string into a LogLevel.
        Defaults to INFO if parsing fails.
        """
        try:
            return cls[level_str.strip().upper()]
        except KeyError:
            return cls.INFO
