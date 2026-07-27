"""
JARVIS AIOS Error Model

Provides the canonical failure framework for typed, contextual, and securely logged
exceptions across the entire operating system.
"""

from .enums import ErrorCategory, ErrorSeverity
from .base import JarvisError
from .hierarchy import (
    ValidationError, ConfigurationError, SecurityError, PermissionError,
    NetworkError, ProviderError, TimeoutError, WorkflowError, MemoryError,
    ToolError, PluginError, InternalError, FatalError, TransientError
)
from .handler import ErrorHandler

__all__ = [
    "ErrorCategory", "ErrorSeverity",
    "JarvisError",
    "ValidationError", "ConfigurationError", "SecurityError", "PermissionError",
    "NetworkError", "ProviderError", "TimeoutError", "WorkflowError", "MemoryError",
    "ToolError", "PluginError", "InternalError", "FatalError", "TransientError",
    "ErrorHandler"
]
