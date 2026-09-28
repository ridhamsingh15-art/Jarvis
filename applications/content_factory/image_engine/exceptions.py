"""
Exceptions for the Image Generation Engine.
"""

from core.exceptions import JarvisError


class ImageEngineError(JarvisError):
    """Base exception for all Image Engine errors."""


class ImageAdapterError(ImageEngineError):
    """Raised when an adapter fails to communicate with its backend (or mock backend)."""


class ImageQualityError(ImageEngineError):
    """Raised when an image fails the quality heuristic checks."""


class ImageValidationError(ImageEngineError):
    """Raised when the resulting image structure or metadata is invalid."""
