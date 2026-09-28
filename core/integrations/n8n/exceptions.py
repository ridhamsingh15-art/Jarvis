"""
Exceptions for the n8n Capability subsystem.
"""

from core.exceptions import JarvisError


class N8nError(JarvisError):
    """Base exception for all n8n errors."""


class N8nConnectionError(N8nError):
    """Raised when n8n is unreachable or authentication fails."""


class N8nExecutionError(N8nError):
    """Raised when an n8n workflow fails to execute."""


class N8nWorkflowNotFoundError(N8nError):
    """Raised when an requested workflow is not registered or found."""
