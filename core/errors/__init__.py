"""
JARVIS AIOS Error Model

Provides the canonical failure framework for typed, contextual, and securely logged
exceptions across the entire operating system.
"""

from .base import JarvisError
from .enums import ErrorCategory, ErrorSeverity
from .handler import ErrorHandler
from .hierarchy import (
    ConfigurationError,
    FatalError,
    InternalError,
    MemoryError,
    NetworkError,
    PermissionError,
    PluginError,
    ProviderError,
    SecurityError,
    TimeoutError,
    ToolError,
    TransientError,
    ValidationError,
    WorkflowError,
)

__all__ = [
    "ConfigurationError",
    "ErrorCategory",
    "ErrorHandler",
    "ErrorSeverity",
    "FatalError",
    "InternalError",
    "JarvisError",
    "MemoryError",
    "NetworkError",
    "PermissionError",
    "PluginError",
    "ProviderError",
    "SecurityError",
    "TimeoutError",
    "ToolError",
    "TransientError",
    "ValidationError",
    "WorkflowError"
]
