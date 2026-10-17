"""
Exceptions for the Animation Engine.
"""

from core.errors import JarvisError


class AnimationEngineError(JarvisError):
    """Base exception for the animation engine."""
    def __init__(self, message: str) -> None:
        super().__init__(message)


class AnimationAdapterError(AnimationEngineError):
    """Raised when an adapter fails to communicate with its backend model."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_code = "ANIMATION_ADAPTER_ERROR"


class AnimationQualityError(AnimationEngineError):
    """Raised when the generated animation fails heuristic quality checks."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_code = "ANIMATION_QUALITY_ERROR"
