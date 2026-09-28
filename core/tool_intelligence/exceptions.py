"""
Exceptions for the Tool Intelligence subsystem.
"""

from core.exceptions import JarvisError


class ToolIntelligenceError(JarvisError):
    """Base exception for all tool intelligence failures."""


class RepairFailedError(ToolIntelligenceError):
    """Raised when the payload repair pipeline cannot safely fix the payload."""


class SchemaResolutionError(ToolIntelligenceError):
    """Raised when the expected action schema cannot be found."""
