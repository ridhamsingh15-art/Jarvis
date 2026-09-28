"""
Validator for Voice Engine Metadata.
"""

from core.errors import JarvisError
from .models import VoiceMetadata


class VoiceValidatorError(JarvisError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class VoiceValidator:
    """Validates the structure and constraints of VoiceMetadata."""
    
    def validate_metadata(self, metadata: VoiceMetadata) -> None:
        if metadata.scene_number <= 0:
            raise VoiceValidatorError(f"Invalid scene number: {metadata.scene_number}")
        if metadata.duration_seconds <= 0:
            raise VoiceValidatorError("Duration must be positive")
        if not metadata.model_name:
            raise VoiceValidatorError("Model name is required")
        if not metadata.text:
            raise VoiceValidatorError("Text is required")
