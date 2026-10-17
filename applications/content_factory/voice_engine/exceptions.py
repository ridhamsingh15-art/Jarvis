"""
Exceptions for the Voice Engine.
"""

from core.errors import JarvisError


class VoiceEngineError(JarvisError):
    """Base exception for the voice engine."""
    def __init__(self, message: str) -> None:
        super().__init__(message)


class VoiceAdapterError(VoiceEngineError):
    """Raised when an adapter fails to communicate with its backend model."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_code = "VOICE_ADAPTER_ERROR"


class VoiceQualityError(VoiceEngineError):
    """Raised when the generated voice fails heuristic quality checks."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_code = "VOICE_QUALITY_ERROR"
