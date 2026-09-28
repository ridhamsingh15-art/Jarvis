from core.exceptions import JarvisError


class IdentityError(JarvisError):
    """Base exception for identity subsystem operations."""


class GuardrailViolation(IdentityError):
    """Raised when a guardrail rewrites a response to maintain JARVIS identity."""
