"""
Exceptions for the Video Engine.
"""

from core.errors import JarvisError


class VideoEngineError(JarvisError):
    """Base exception for the video engine."""
    def __init__(self, message: str) -> None:
        super().__init__(message)


class TimelineError(VideoEngineError):
    """Raised when there is an issue building the timeline (missing clips, bad sync)."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_code = "TIMELINE_ERROR"


class FFmpegError(VideoEngineError):
    """Raised when the FFmpeg adapter fails to render the video."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_code = "FFMPEG_ERROR"
