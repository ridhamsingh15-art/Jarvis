"""
Validator for Animation Engine Metadata.
"""

from core.errors import JarvisError
from .models import AnimationMetadata


class AnimationValidatorError(JarvisError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class AnimationValidator:
    """Validates the structure and constraints of AnimationMetadata."""
    
    def validate_metadata(self, metadata: AnimationMetadata) -> None:
        if metadata.scene_number <= 0:
            raise AnimationValidatorError(f"Invalid scene number: {metadata.scene_number}")
        if metadata.duration_seconds <= 0:
            raise AnimationValidatorError("Duration must be positive")
        if metadata.fps <= 0:
            raise AnimationValidatorError("FPS must be positive")
        if not metadata.model_name:
            raise AnimationValidatorError("Model name is required")
