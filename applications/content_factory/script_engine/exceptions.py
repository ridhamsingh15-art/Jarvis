"""
Exceptions for the Script Generation Engine.
"""

from core.exceptions import JarvisError


class ScriptEngineError(JarvisError):
    """Base exception for all Script Engine errors."""


class ScriptValidationError(ScriptEngineError):
    """Raised when a generated script fails validation."""


class ScriptQualityError(ScriptEngineError):
    """Raised when a generated script fails quality review thresholds."""


class ScriptFormatError(ScriptEngineError):
    """Raised when the LLM output cannot be parsed into the expected JSON structure."""
