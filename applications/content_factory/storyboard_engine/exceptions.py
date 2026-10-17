"""
Exceptions for the Storyboard Engine.
"""

from core.exceptions import JarvisError


class StoryboardEngineError(JarvisError):
    """Base exception for all Storyboard Engine errors."""


class StoryboardValidationError(StoryboardEngineError):
    """Raised when a generated storyboard fails validation."""


class StoryboardQualityError(StoryboardEngineError):
    """Raised when a generated storyboard fails quality review thresholds."""


class StoryboardFormatError(StoryboardEngineError):
    """Raised when the LLM output cannot be parsed into the expected JSON structure."""
