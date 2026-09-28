import os
import sys
from abc import ABC, abstractmethod


class LogSink(ABC):
    """
    Abstract interface for a destination where logs are written.
    """
    @abstractmethod
    def write(self, formatted_log: str) -> None:
        """Writes a formatted log string to the sink."""
        
    def close(self) -> None:
        """Optional cleanup routine for the sink."""


class ConsoleSink(LogSink):
    """
    Writes logs to standard output (stdout).
    """
    def write(self, formatted_log: str) -> None:
        try:
            sys.stdout.write(formatted_log + "\n")
            sys.stdout.flush()
        except (OSError, UnicodeEncodeError):
            # Silent fail to prevent crashing if stdout is broken
            pass


class FileSink(LogSink):
    """
    Writes logs to a file.
    """
    def __init__(self, file_path: str):
        self.file_path = file_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        # Open in append mode with unbuffered or line-buffered behavior ideally, 
        # but we use standard buffering for performance and flush explicitly or on close.
        self._file = open(self.file_path, "a", encoding="utf-8")  # noqa: SIM115

    def write(self, formatted_log: str) -> None:
        if not self._file.closed:
            try:
                self._file.write(formatted_log + "\n")
                self._file.flush()
            except OSError:
                # Silently fail rather than crashing the logging thread
                pass

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()
