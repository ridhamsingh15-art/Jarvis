"""
Validator for Video Engine Metadata.
"""

from core.errors import JarvisError
from .models import VideoMetadata


class VideoValidatorError(JarvisError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class VideoValidator:
    """Validates the structure and constraints of VideoMetadata."""
    
    def validate_metadata(self, metadata: VideoMetadata) -> None:
        if metadata.duration_seconds <= 0:
            raise VideoValidatorError("Duration must be positive")
        if not metadata.resolution:
            raise VideoValidatorError("Resolution is required")
        if metadata.fps <= 0:
            raise VideoValidatorError("FPS must be positive")
        if not metadata.codec:
            raise VideoValidatorError("Codec is required")
