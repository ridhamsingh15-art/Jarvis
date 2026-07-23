"""
Custom exception hierarchy for Jarvis.

Every exception inherits from JarvisError so callers can catch
all framework errors with a single except clause, or target
specific failure modes individually.
"""


class JarvisError(Exception):
    """Base exception for all Jarvis framework errors."""


class LLMConnectionError(JarvisError):
    """Raised when the LLM backend (Ollama) is unreachable."""


class ParseError(JarvisError):
    """Raised when JSON extraction from LLM output fails."""


class ValidationError(JarvisError):
    """Raised when a Task fails validation (unknown tool, action, or args)."""


class ExecutionError(JarvisError):
    """Raised when a tool execution fails."""


class InvalidStateError(JarvisError):
    """Raised when a Task undergoes an illegal state transition."""


class MemoryError(JarvisError):
    """Raised when a memory storage or retrieval operation fails."""
